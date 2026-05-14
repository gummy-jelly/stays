from fastapi import APIRouter, Depends

from app.database import get_pool
from app.auth import get_current_user
from app.schemas import NotificationItem

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/me", response_model=list[NotificationItem])
async def get_my_notifications(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::TEXT, booking_id::TEXT, message, is_read, created_at::TEXT
            FROM notifications
            WHERE user_id = $1::UUID
            ORDER BY created_at DESC
            LIMIT 50
            """,
            current_user["id"],
        )
    return [NotificationItem(**dict(r)) for r in rows]


@router.patch("/me/read")
async def mark_all_read(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE notifications SET is_read = TRUE WHERE user_id = $1::UUID",
            current_user["id"],
        )
    return {"message": "모든 알림을 읽음으로 표시했습니다"}
