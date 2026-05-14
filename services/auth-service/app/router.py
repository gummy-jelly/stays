from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    delete_refresh_token,
    get_current_user_id,
    get_stored_refresh_token,
    hash_password,
    store_refresh_token,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_WRONG_CREDENTIALS = "이메일 또는 비밀번호가 올바르지 않습니다"


# ── 회원가입 ──────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 가입된 이메일입니다",
        )

    user = User(
        name=req.name,
        email=req.email,
        password=hash_password(req.password),
        phone=req.phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    store_refresh_token(str(user.id), refresh_token)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ── 로그인 ────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()

    # 이메일/비밀번호 중 어느 쪽이 틀렸는지 노출 금지 — 동일 메시지
    if not user or not verify_password(req.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_WRONG_CREDENTIALS,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다",
        )

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    store_refresh_token(str(user.id), refresh_token)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ── 로그아웃 ──────────────────────────────────

@router.post("/logout")
def logout(user_id: str = Depends(get_current_user_id)):
    delete_refresh_token(user_id)
    return {"message": "로그아웃 되었습니다"}


# ── Access Token 갱신 ─────────────────────────

@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(req.refresh_token, "refresh")
    user_id: str = payload["sub"]

    stored = get_stored_refresh_token(user_id)
    if not stored or stored != req.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # 활성 유저 확인
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다",
        )

    # Refresh Token Rotation — 기존 토큰 무효화 후 새 토큰 발급
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)
    store_refresh_token(user_id, new_refresh)

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


# ── 내 정보 조회 ──────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_me(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다",
        )
    return user
