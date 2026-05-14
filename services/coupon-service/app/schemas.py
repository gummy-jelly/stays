from pydantic import BaseModel
from typing import Optional


class IssueRequest(BaseModel):
    event_id: str
    coupon_code: str


class ValidateRequest(BaseModel):
    coupon_code: str
    stay_id: Optional[str] = None


class CouponResult(BaseModel):
    id: str
    code: str
    event_id: Optional[str] = None
    stay_id: Optional[str] = None
    discount_rate: int
    is_used: bool
    remaining_count: int
    total_count: int


class ValidateResult(BaseModel):
    valid: bool
    discount_rate: int = 0
    message: str
    coupon_id: Optional[str] = None
