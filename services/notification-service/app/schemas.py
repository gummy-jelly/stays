from pydantic import BaseModel
from typing import Optional


class NotificationItem(BaseModel):
    id: str
    booking_id: Optional[str] = None
    message: str
    is_read: bool
    created_at: str
