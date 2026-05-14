"""
Redis Pub/Sub 구독자 — booking.confirmed 채널 수신 → notifications 테이블 저장
booking-service가 다운되어도 예약은 영향 없음 (비동기 패턴)
"""
import asyncio
import json
import logging

import redis.asyncio as aioredis

from app.config import get_settings
from app.database import get_pool

logger = logging.getLogger("notification.subscriber")


async def subscribe_booking_events() -> None:
    settings = get_settings()
    while True:
        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            pubsub = r.pubsub()
            await pubsub.subscribe("booking.confirmed")
            logger.info("Redis 구독 시작: booking.confirmed")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    await _save_notification(data)
                except Exception as e:
                    logger.error("알림 저장 실패: %s", e)

        except Exception as e:
            logger.error("Redis 연결 실패, 5초 후 재시도: %s", e)
            await asyncio.sleep(5)


async def _save_notification(data: dict) -> None:
    pool = await get_pool()
    user_id = data.get("user_id")
    booking_id = data.get("booking_id")
    stay_name = data.get("stay_name", "숙소")
    check_in = data.get("check_in", "")
    check_out = data.get("check_out", "")
    total_price = data.get("total_price", 0)

    message = (
        f"[예약 완료] {stay_name} | "
        f"{check_in} ~ {check_out} | "
        f"결제금액 {total_price:,}원"
    )

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO notifications (user_id, booking_id, message)
            VALUES ($1::UUID, $2::UUID, $3)
            """,
            user_id, booking_id, message,
        )
    logger.info("알림 저장 완료: user=%s booking=%s", user_id, booking_id)
