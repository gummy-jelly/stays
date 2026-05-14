import json
import logging
from datetime import date
from fastapi import APIRouter, HTTPException, Depends, status

logger = logging.getLogger("booking.router")

from app.database import get_pool
from app.auth import get_current_user
from app.schemas import BookingRequest, BookingResult

router = APIRouter(prefix="/bookings", tags=["bookings"])

CLEANING_FEE = 30000
SERVICE_FEE_RATE = 0.05


def _nights(check_in: str, check_out: str) -> int:
    ci = date.fromisoformat(check_in)
    co = date.fromisoformat(check_out)
    nights = (co - ci).days
    if nights <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="체크아웃은 체크인 이후여야 합니다")
    return nights


@router.post("", response_model=BookingResult, status_code=status.HTTP_201_CREATED)
async def create_booking(req: BookingRequest, current_user: dict = Depends(get_current_user)):
    """
    예약 생성 — rooms, coupons 테이블 단일 트랜잭션 처리 (공유 DB 전략)
    """
    nights = _nights(req.check_in, req.check_out)
    pool = await get_pool()
    user_id = current_user["id"]

    async with pool.acquire() as conn:
        async with conn.transaction():
            # 객실 잠금 + 재고 확인 (FOR UPDATE)
            room = await conn.fetchrow(
                """
                SELECT r.id::TEXT, r.name,
                       r.price_per_night AS price,
                       r.max_guests, r.remaining_count,
                       s.name AS stay_name
                FROM rooms r
                JOIN stays s ON s.id = r.stay_id
                WHERE r.id = $1::UUID AND r.stay_id = $2::UUID
                FOR UPDATE OF r
                """,
                req.room_id, req.stay_id,
            )
            if not room:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="객실을 찾을 수 없습니다")
            if room["remaining_count"] <= 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="선택한 객실의 재고가 없습니다")
            if req.guests > room["max_guests"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"최대 인원은 {room['max_guests']}명입니다",
                )

            # 객실 재고 차감
            await conn.execute(
                "UPDATE rooms SET remaining_count = remaining_count - 1 WHERE id = $1::UUID",
                req.room_id,
            )

            # 가격 계산
            original_price = room["price"] * nights
            cleaning_fee = CLEANING_FEE
            service_fee = int(original_price * SERVICE_FEE_RATE)
            discount_amount = 0

            # 쿠폰 처리
            coupon_id = None
            if req.coupon_id:
                coupon = await conn.fetchrow(
                    """
                    SELECT id::TEXT, discount_rate FROM coupons
                    WHERE id = $1::UUID AND used_by = $2::UUID AND is_used = FALSE
                    FOR UPDATE
                    """,
                    req.coupon_id, user_id,
                )
                if coupon:
                    discount_amount = int(original_price * coupon["discount_rate"] / 100)
                    await conn.execute(
                        "UPDATE coupons SET is_used = TRUE WHERE id = $1::UUID",
                        req.coupon_id,
                    )
                    coupon_id = coupon["id"]

            # 이벤트 할인 처리 (쿠폰 없을 때)
            elif req.event_id:
                event_stay = await conn.fetchrow(
                    """
                    SELECT discount_rate FROM event_stays
                    WHERE event_id = $1::UUID AND stay_id = $2::UUID
                    """,
                    req.event_id, req.stay_id,
                )
                if event_stay:
                    discount_amount = int(original_price * event_stay["discount_rate"] / 100)

            total_price = original_price + cleaning_fee + service_fee - discount_amount

            # 예약 생성
            booking = await conn.fetchrow(
                """
                INSERT INTO bookings (
                    user_id, stay_id, stay_name, room_id, room_name,
                    check_in, check_out, guests,
                    original_price, cleaning_fee, service_fee, discount_amount, total_price,
                    coupon_id, event_id
                ) VALUES (
                    $1::UUID, $2::UUID, $3, $4::UUID, $5,
                    $6::DATE, $7::DATE, $8,
                    $9, $10, $11, $12, $13,
                    $14::UUID, $15::UUID
                )
                RETURNING id::TEXT, stay_id::TEXT, stay_name, room_id::TEXT, room_name,
                          check_in::TEXT, check_out::TEXT, guests,
                          original_price, cleaning_fee, service_fee, discount_amount, total_price,
                          status, created_at::TEXT
                """,
                user_id, req.stay_id, room["stay_name"], req.room_id, room["name"],
                req.check_in, req.check_out, req.guests,
                original_price, cleaning_fee, service_fee, discount_amount, total_price,
                coupon_id, req.event_id,
            )

    # Redis 이벤트 발행 (notification-service 트리거) — 실패해도 예약에 영향 없음
    await _publish_booking_event(dict(booking), current_user)

    return BookingResult(**dict(booking))


async def _publish_booking_event(booking: dict, user: dict):
    try:
        from app.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        if not settings.REDIS_URL:
            return

        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        payload = json.dumps({
            "booking_id": booking["id"],
            "user_id": user["id"],
            "stay_name": booking["stay_name"],
            "check_in": booking["check_in"],
            "check_out": booking["check_out"],
            "total_price": booking["total_price"],
        })
        await r.publish("booking.confirmed", payload)
        await r.aclose()
    except Exception as e:
        logger.warning("Redis 이벤트 발행 실패 (무시): %s", e)


@router.get("/me", response_model=list[BookingResult])
async def get_my_bookings(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::TEXT, stay_id::TEXT, stay_name, room_id::TEXT, room_name,
                   check_in::TEXT, check_out::TEXT, guests,
                   original_price, cleaning_fee, service_fee, discount_amount, total_price,
                   status, created_at::TEXT
            FROM bookings
            WHERE user_id = $1::UUID
            ORDER BY created_at DESC
            """,
            current_user["id"],
        )
    return [BookingResult(**dict(r)) for r in rows]


@router.get("/{booking_id}", response_model=BookingResult)
async def get_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::TEXT, stay_id::TEXT, stay_name, room_id::TEXT, room_name,
                   check_in::TEXT, check_out::TEXT, guests,
                   original_price, cleaning_fee, service_fee, discount_amount, total_price,
                   status, created_at::TEXT
            FROM bookings
            WHERE id = $1::UUID AND user_id = $2::UUID
            """,
            booking_id, current_user["id"],
        )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="예약을 찾을 수 없습니다")
    return BookingResult(**dict(row))
