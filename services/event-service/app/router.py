from fastapi import APIRouter, HTTPException, status

from app.database import get_pool
from app.schemas import EventItem, EventDetail, EventStayItem

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventItem])
async def list_events():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::TEXT, title, description,
                   type, region,
                   COALESCE(start_date::TEXT, '') AS start_date,
                   COALESCE(end_date::TEXT, '')   AS end_date,
                   total_rooms, remaining_rooms,
                   discount_rate AS max_discount,
                   status, banner_color
            FROM events
            WHERE status IN ('ongoing', 'active', 'upcoming')
            ORDER BY start_date ASC NULLS LAST
            """
        )
    return [EventItem(**dict(r)) for r in rows]


@router.get("/{event_id}", response_model=EventDetail)
async def get_event(event_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::TEXT, title, description,
                   type, region,
                   COALESCE(start_date::TEXT, '') AS start_date,
                   COALESCE(end_date::TEXT, '')   AS end_date,
                   total_rooms, remaining_rooms,
                   discount_rate AS max_discount,
                   status, banner_color
            FROM events
            WHERE id = $1::UUID
            """,
            event_id,
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="이벤트를 찾을 수 없습니다")

        stay_rows = await conn.fetch(
            """
            SELECT s.id::TEXT AS stay_id, s.name, s.region AS location, s.category,
                   s.rating, s.review_count AS reviews, s.price_per_night AS price,
                   COALESCE(
                       s.image_url,
                       (SELECT url FROM stay_images si
                        WHERE si.stay_id = s.id AND si.is_main = TRUE LIMIT 1)
                   ) AS image_url,
                   es.discount_rate, es.remaining_rooms
            FROM event_stays es
            JOIN stays s ON s.id = es.stay_id
            WHERE es.event_id = $1::UUID
            ORDER BY es.discount_rate DESC
            """,
            event_id,
        )

    stays = [
        EventStayItem(
            stay_id=r["stay_id"], name=r["name"], location=r["location"],
            category=r["category"], rating=float(r["rating"]),
            reviews=r["reviews"], price=r["price"],
            image_url=r["image_url"], discount_rate=r["discount_rate"],
            remaining_rooms=r["remaining_rooms"],
        )
        for r in stay_rows
    ]

    return EventDetail(**dict(row), stays=stays)
