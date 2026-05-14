import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_pool, close_pool
from app.router import router
from app.subscriber import subscribe_booking_events

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    # Redis 구독 백그라운드 태스크 시작
    task = asyncio.create_task(subscribe_booking_events())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await close_pool()


app = FastAPI(
    title="Notification Service",
    description="Redis Pub/Sub → 예약 완료 알림 저장 / 조회",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"service": "notification-service", "status": "ok"}
