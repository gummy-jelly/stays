from fastapi import APIRouter, HTTPException, Query, status

from app.database import get_pool
from app.schemas import StayItem, StayDetail, RoomItem, ReviewItem

router = APIRouter(prefix="/stays", tags=["stays"])

# 목록/상세 공통 SELECT — DB 컬럼명(region/lat/lng/price_per_night/review_count)을
# 프론트엔드가 기대하는 필드명으로 AS 처리
_STAY_LIST_COLS = """
    s.id::TEXT,
    s.name,
    s.region         AS location,
    s.category,
    s.tags,
    s.rating,
    s.review_count   AS reviews,
    s.price_per_night AS price,
    COALESCE(
        s.image_url,
        (SELECT url FROM stay_images si WHERE si.stay_id = s.id AND si.is_main = TRUE LIMIT 1)
    )                AS image_url,
    s.badge,
    s.lat            AS latitude,
    s.lng            AS longitude,
    s.address
"""


@router.get("", response_model=list[StayItem])
async def list_stays(
    category: str = Query(None),
    region: str = Query(None),
    search: str = Query(None),
    sort: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    pool = await get_pool()
    conditions = []
    params: list = []

    if category:
        params.append(category)
        conditions.append(f"s.category = ${len(params)}")
    if region:
        params.append(f"%{region}%")
        conditions.append(f"s.region ILIKE ${len(params)}")
    if search:
        params.append(f"%{search}%")
        conditions.append(f"(s.name ILIKE ${len(params)} OR s.region ILIKE ${len(params)})")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    order = "s.rating DESC"
    if sort == "price_asc":
        order = "s.price_per_night ASC"
    elif sort == "price_desc":
        order = "s.price_per_night DESC"
    elif sort == "reviews":
        order = "s.review_count DESC"

    params.append(limit)
    params.append(offset)

    sql = f"""
        SELECT {_STAY_LIST_COLS}
        FROM stays s
        {where}
        ORDER BY {order}
        LIMIT ${len(params)-1} OFFSET ${len(params)}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [
        StayItem(
            id=r["id"], name=r["name"], location=r["location"],
            category=r["category"], tags=list(r["tags"] or []),
            rating=float(r["rating"]), reviews=r["reviews"],
            price=r["price"], image_url=r["image_url"], badge=r["badge"],
            latitude=float(r["latitude"]) if r["latitude"] is not None else None,
            longitude=float(r["longitude"]) if r["longitude"] is not None else None,
            address=r["address"],
        )
        for r in rows
    ]


@router.get("/{stay_id}", response_model=StayDetail)
async def get_stay(stay_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT {_STAY_LIST_COLS},
                   s.description,
                   s.max_guests,
                   COALESCE(s.bedrooms, 1)   AS bedrooms,
                   COALESCE(s.bathrooms, 1)  AS bathrooms,
                   s.host_name
            FROM stays s
            WHERE s.id = $1::UUID
            """,
            stay_id,
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="숙소를 찾을 수 없습니다")

        amenities = await conn.fetch(
            """
            SELECT a.name FROM amenities a
            JOIN stay_amenities sa ON sa.amenity_id = a.id
            WHERE sa.stay_id = $1::UUID
            ORDER BY a.name
            """,
            stay_id,
        )
        images = await conn.fetch(
            "SELECT url FROM stay_images WHERE stay_id = $1::UUID ORDER BY is_main DESC",
            stay_id,
        )

    return StayDetail(
        id=row["id"], name=row["name"], location=row["location"],
        category=row["category"], tags=list(row["tags"] or []),
        rating=float(row["rating"]), reviews=row["reviews"],
        price=row["price"], image_url=row["image_url"], badge=row["badge"],
        latitude=float(row["latitude"]) if row["latitude"] is not None else None,
        longitude=float(row["longitude"]) if row["longitude"] is not None else None,
        address=row["address"], description=row["description"],
        max_guests=row["max_guests"], bedrooms=row["bedrooms"],
        bathrooms=row["bathrooms"], host_name=row["host_name"],
        amenities=[a["name"] for a in amenities],
        images=[img["url"] for img in images],
    )


@router.get("/{stay_id}/rooms", response_model=list[RoomItem])
async def get_stay_rooms(stay_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM stays WHERE id = $1::UUID", stay_id)
        if not exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="숙소를 찾을 수 없습니다")

        rows = await conn.fetch(
            """
            SELECT id::TEXT,
                   name,
                   room_count,
                   remaining_count,
                   price_per_night AS price,
                   max_guests
            FROM rooms
            WHERE stay_id = $1::UUID
            ORDER BY price_per_night
            """,
            stay_id,
        )

    return [RoomItem(**dict(r)) for r in rows]


@router.get("/{stay_id}/reviews", response_model=list[ReviewItem])
async def get_stay_reviews(stay_id: str, limit: int = Query(10, ge=1, le=50)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT r.id::TEXT,
                   r.rating,
                   r.content,
                   r.created_at::TEXT,
                   COALESCE(u.name, '익명') AS user_name
            FROM reviews r
            LEFT JOIN users u ON u.id = r.user_id
            WHERE r.stay_id = $1::UUID
            ORDER BY r.created_at DESC
            LIMIT $2
            """,
            stay_id, limit,
        )

    return [ReviewItem(**dict(r)) for r in rows]
