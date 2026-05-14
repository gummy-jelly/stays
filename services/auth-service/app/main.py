import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.router import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("auth.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB 초기화: blocking 작업을 thread pool에서 실행해 이벤트 루프 블로킹 방지
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, init_db)
    logger.info("auth-service 시작 완료")
    yield
    logger.info("auth-service 종료")


app = FastAPI(
    title="Auth Service",
    description="회원가입 / 로그인 / JWT 발급 / Refresh Token (Redis)",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "service": "auth-service"}
