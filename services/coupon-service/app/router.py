from fastapi import APIRouter, HTTPException, Depends, status

from app.database import get_pool
from app.auth import get_current_user
from app.schemas import IssueRequest, ValidateRequest, CouponResult, ValidateResult

router = APIRouter(prefix="/coupons", tags=["coupons"])


@router.post("/issue", response_model=CouponResult, status_code=status.HTTP_201_CREATED)
async def issue_coupon(req: IssueRequest, current_user: dict = Depends(get_current_user)):
    """
    쿠폰 발급 — HPA 데모 핵심 엔드포인트
    SELECT ... FOR UPDATE 비관적 락으로 재고 차감
    """
    pool = await get_pool()
    user_id = current_user["id"]

    async with pool.acquire() as conn:
        async with conn.transaction():
            # 이미 발급받았는지 확인
            already = await conn.fetchrow(
                """
                SELECT id FROM coupons
                WHERE code = $1 AND used_by = $2::UUID
                """,
                req.coupon_code, user_id,
            )
            if already:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="이미 발급받은 쿠폰입니다",
                )

            # 마스터 쿠폰 잠금 (FOR UPDATE)
            master = await conn.fetchrow(
                """
                SELECT id::TEXT, code, event_id::TEXT, stay_id::TEXT,
                       discount_rate, remaining_count, total_count
                FROM coupons
                WHERE code = $1 AND used_by IS NULL
                FOR UPDATE
                """,
                req.coupon_code,
            )
            if not master:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="존재하지 않는 쿠폰 코드입니다",
                )
            if master["remaining_count"] <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="쿠폰이 모두 소진되었습니다",
                )

            # 재고 차감
            await conn.execute(
                "UPDATE coupons SET remaining_count = remaining_count - 1 WHERE id = $1::UUID",
                master["id"],
            )

            # 사용자 쿠폰 발급
            new_row = await conn.fetchrow(
                """
                INSERT INTO coupons (code, event_id, stay_id, discount_rate,
                                     remaining_count, total_count, used_by)
                VALUES ($1, $2::UUID, $3::UUID, $4, 1, 1, $5::UUID)
                RETURNING id::TEXT, code, event_id::TEXT, stay_id::TEXT,
                          discount_rate, is_used, remaining_count, total_count
                """,
                master["code"],
                master["event_id"],
                master["stay_id"],
                master["discount_rate"],
                user_id,
            )

    return CouponResult(**dict(new_row))


@router.get("/me", response_model=list[CouponResult])
async def get_my_coupons(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::TEXT, code, event_id::TEXT, stay_id::TEXT,
                   discount_rate, is_used, remaining_count, total_count
            FROM coupons
            WHERE used_by = $1::UUID AND is_used = FALSE
            ORDER BY created_at DESC
            """,
            current_user["id"],
        )
    return [CouponResult(**dict(r)) for r in rows]


@router.post("/validate", response_model=ValidateResult)
async def validate_coupon(req: ValidateRequest, current_user: dict = Depends(get_current_user)):
    """
    쿠폰 유효성 검증 — 마스터 재고 확인
    예약 전 할인율 미리 확인용
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 사용자가 이미 발급받은 쿠폰 확인
        user_coupon = await conn.fetchrow(
            """
            SELECT id::TEXT, discount_rate FROM coupons
            WHERE code = $1 AND used_by = $2::UUID AND is_used = FALSE
            """,
            req.coupon_code, current_user["id"],
        )
        if user_coupon:
            return ValidateResult(
                valid=True,
                discount_rate=user_coupon["discount_rate"],
                message="사용 가능한 쿠폰입니다",
                coupon_id=user_coupon["id"],
            )

        # 마스터 재고 확인
        master = await conn.fetchrow(
            """
            SELECT discount_rate, remaining_count FROM coupons
            WHERE code = $1 AND used_by IS NULL
            """,
            req.coupon_code,
        )
        if not master:
            return ValidateResult(valid=False, message="존재하지 않는 쿠폰 코드입니다")
        if master["remaining_count"] <= 0:
            return ValidateResult(valid=False, message="쿠폰이 모두 소진되었습니다")

    return ValidateResult(
        valid=True,
        discount_rate=master["discount_rate"],
        message="발급 가능한 쿠폰입니다",
    )
