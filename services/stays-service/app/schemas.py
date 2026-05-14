from pydantic import BaseModel
from typing import Optional


class StayItem(BaseModel):
    id: str
    name: str
    location: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = []
    rating: float = 0
    reviews: int = 0
    price: int
    image_url: Optional[str] = None
    badge: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None


class StayDetail(StayItem):
    description: Optional[str] = None
    max_guests: int = 2
    bedrooms: int = 1
    bathrooms: int = 1
    host_name: Optional[str] = None
    amenities: list[str] = []
    images: list[str] = []


class RoomItem(BaseModel):
    id: str
    name: str
    room_count: int
    remaining_count: int
    price: int
    max_guests: int


class ReviewItem(BaseModel):
    id: str
    rating: int
    content: str
    created_at: str
    user_name: str
