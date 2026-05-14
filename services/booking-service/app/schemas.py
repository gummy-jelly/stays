from pydantic import BaseModel
from typing import Optional


class BookingRequest(BaseModel):
    stay_id: str
    room_id: str
    check_in: str
    check_out: str
    guests: int
    coupon_id: Optional[str] = None
    event_id: Optional[str] = None


class BookingResult(BaseModel):
    id: str
    stay_id: str
    stay_name: Optional[str] = None
    room_id: str
    room_name: Optional[str] = None
    check_in: str
    check_out: str
    guests: int
    original_price: int
    cleaning_fee: int
    service_fee: int
    discount_amount: int
    total_price: int
    status: str
    created_at: str
