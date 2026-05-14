from pydantic import BaseModel
from typing import Optional


class EventItem(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    type: Optional[str] = None
    region: Optional[str] = None
    start_date: str
    end_date: str
    total_rooms: int = 0
    remaining_rooms: int = 0
    max_discount: Optional[int] = None   # DB: discount_rate (이벤트 전체 최대 할인율)
    status: str = "upcoming"
    banner_color: Optional[str] = None


class EventStayItem(BaseModel):
    stay_id: str
    name: str
    location: Optional[str] = None
    category: Optional[str] = None
    rating: float = 0
    reviews: int = 0
    price: int
    image_url: Optional[str] = None
    discount_rate: int = 0              # DB: event_stays.discount_rate (숙소별 할인율)
    remaining_rooms: int = 0


class EventDetail(EventItem):
    stays: list[EventStayItem] = []
