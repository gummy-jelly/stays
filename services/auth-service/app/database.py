import logging
import time
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

from app.config import get_settings

logger = logging.getLogger("auth.database")


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def init_db(max_retries: int = 10, retry_interval: int = 5) -> None:
    """DB 연결 + 테이블 자동 생성. 연결 실패 시 재시도."""
    global _engine, _SessionLocal

    settings = get_settings()

    for attempt in range(1, max_retries + 1):
        try:
            engine = create_engine(
                settings.DATABASE_URL,
                pool_pre_ping=True,      # 연결 헬스체크
                pool_size=5,
                max_overflow=10,
            )
            # 연결 확인
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            # import here to register models before create_all
            from app import models  # noqa: F401

            Base.metadata.create_all(bind=engine)

            _engine = engine
            _SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
            logger.info("DB 연결 성공 (attempt %d)", attempt)
            return

        except Exception as exc:
            logger.warning(
                "DB 연결 실패 (%d/%d): %s — %ds 후 재시도",
                attempt, max_retries, exc, retry_interval,
            )
            if attempt < max_retries:
                time.sleep(retry_interval)

    raise RuntimeError("DB에 연결할 수 없습니다. 서버를 종료합니다.")


def get_db() -> Generator[Session, None, None]:
    if _SessionLocal is None:
        raise RuntimeError("DB pool not initialized.")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
