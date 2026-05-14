# Auth Service

숙박 예약 플랫폼의 인증 서비스.  
회원가입 / 로그인 / JWT 발급 / Redis Refresh Token 관리를 담당한다.

---

## 기술 스택

| 항목 | 버전 | 역할 |
|---|---|---|
| Python | 3.11.9 | 런타임 |
| FastAPI | 0.111.0 | 웹 프레임워크 |
| uvicorn | 0.29.0 | ASGI 서버 |
| SQLAlchemy | 2.0.30 | ORM (동기 드라이버) |
| psycopg2-binary | 2.9.9 | PostgreSQL 드라이버 |
| python-jose | 3.3.0 | JWT 생성/검증 |
| passlib[bcrypt] | 1.7.4 | 비밀번호 해시 |
| redis | 5.0.4 | Refresh Token 저장소 |
| pydantic | 2.7.1 | 데이터 검증 |
| pydantic-settings | 2.2.1 | 환경변수 관리 |

---

## 파일 구조

```
auth-service/
├── app/
│   ├── __init__.py
│   ├── main.py         앱 진입점, lifespan, CORS, /health
│   ├── router.py       API 엔드포인트 5개
│   ├── schemas.py      Pydantic 요청/응답 스키마
│   ├── models.py       SQLAlchemy User 모델
│   ├── auth.py         JWT, bcrypt, Redis 유틸리티
│   ├── config.py       환경변수 설정 (pydantic-settings)
│   └── database.py     SQLAlchemy 엔진, DB 재시도 로직
├── docker-compose.yml  단독 실행용 (amd64, db + redis 포함)
├── Dockerfile
├── requirements.txt
└── AUTH_SERVICE.md     (이 문서)
```

---

## 실행 방법

### 단독 개발 실행 (이 폴더 기준)

```bash
cd services/auth-service

# 빌드 + 실행
docker compose up --build

# 백그라운드 실행
docker compose up --build -d

# 로그 확인
docker compose logs -f auth-service

# 종료 (볼륨 유지)
docker compose down

# 종료 + 볼륨 삭제 (DB 초기화)
docker compose down -v
```

### 접속 확인

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"auth-service"}
```

---

## API 엔드포인트

| Method | Path | 설명 | 인증 필요 |
|---|---|---|---|
| `POST` | `/auth/register` | 회원가입 | ✗ |
| `POST` | `/auth/login` | 로그인 | ✗ |
| `POST` | `/auth/logout` | 로그아웃 (Redis 토큰 삭제) | ✅ Bearer |
| `POST` | `/auth/refresh` | Access Token 갱신 | ✗ (body에 refresh_token) |
| `GET` | `/auth/me` | 내 정보 조회 | ✅ Bearer |
| `GET` | `/health` | 헬스체크 (K8s용) | ✗ |

---

### `POST /auth/register` — 회원가입

**Request**
```json
{
  "name": "홍길동",
  "email": "user@example.com",
  "password": "password123",
  "phone": "010-1234-5678"
}
```

**Response `201`**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**에러**
| 코드 | 조건 |
|---|---|
| `409` | 이미 가입된 이메일 |
| `422` | 비밀번호 8자 미만 / 필수 필드 누락 |

---

### `POST /auth/login` — 로그인

**Request**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response `200`**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**에러**
| 코드 | 조건 |
|---|---|
| `401` | 이메일 또는 비밀번호가 올바르지 않습니다 (구분 노출 없음) |
| `403` | 비활성화된 계정입니다 |

---

### `POST /auth/logout` — 로그아웃

**Header** `Authorization: Bearer {access_token}`

Redis의 `refresh:{user_id}` 키를 삭제한다.

**Response `200`**
```json
{ "message": "로그아웃 되었습니다" }
```

---

### `POST /auth/refresh` — Access Token 갱신

**Request**
```json
{ "refresh_token": "eyJ..." }
```

**Response `200`**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

> **Refresh Token Rotation**: 갱신 시 기존 Refresh Token 즉시 무효화 + 새 토큰 발급.  
> Refresh Token 재사용 공격 방어.

**에러**
| 코드 | 조건 |
|---|---|
| `401` | 만료된 토큰 |
| `401` | Redis 저장 토큰과 불일치 (`"Invalid refresh token"`) |
| `403` | 비활성화된 계정 |

---

### `GET /auth/me` — 내 정보 조회

**Header** `Authorization: Bearer {access_token}`

**Response `200`**
```json
{
  "id": "uuid",
  "name": "홍길동",
  "email": "user@example.com",
  "phone": "010-1234-5678",
  "is_active": true,
  "is_admin": false,
  "created_at": "2026-05-15T00:00:00+00:00"
}
```

---

### `GET /health` — 헬스체크

**Response `200`**
```json
{ "status": "ok", "service": "auth-service" }
```

---

## 환경변수

| 변수명 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | `postgresql://user:pass@host:5432/db` |
| `JWT_SECRET` | ✅ | — | 32자 이상 랜덤 문자열 (하드코딩 금지) |
| `JWT_EXPIRE` | | `30` | Access Token 만료 (분) |
| `REFRESH_EXPIRE` | | `7` | Refresh Token 만료 (일) |
| `REDIS_URL` | | `redis://localhost:6379/0` | Redis 접속 URL (DB 0번 고정) |
| `SERVICE_PORT` | | `8000` | 서버 포트 |

---

## 토큰 설계

### JWT 페이로드

```json
{
  "sub": "user-uuid",
  "type": "access",
  "exp": 1234567890
}
```

`type` 필드로 Access / Refresh 구분 → 타입 혼용 공격 방어

### Access Token
- 만료: 30분
- `Authorization: Bearer {token}` 헤더로 전달
- 서버에 저장하지 않음 (stateless)

### Refresh Token
- 만료: 7일
- Redis `refresh:{user_id}` 에 저장
- 로그아웃 시 즉시 삭제
- 갱신 시 Rotation (기존 무효화 + 신규 발급)

---

## Redis 저장 구조

```
key   : refresh:{user_id}
value : {refresh_token_string}
TTL   : REFRESH_EXPIRE × 86400초 (기본 604800초 = 7일)
DB    : 0번  (REDIS_URL 끝 /0)
```

---

## DB 모델 (users 테이블)

| 컬럼 | 타입 | 제약 | 기본값 |
|---|---|---|---|
| `id` | UUID | PK | `gen_random_uuid()` |
| `name` | VARCHAR(100) | NOT NULL | — |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | — |
| `password` | VARCHAR(255) | NOT NULL | bcrypt hash |
| `phone` | VARCHAR(20) | NULL 허용 | — |
| `is_active` | BOOLEAN | NOT NULL | `TRUE` |
| `is_admin` | BOOLEAN | NOT NULL | `FALSE` |
| `created_at` | TIMESTAMPTZ | NOT NULL | `NOW()` |

> 앱 시작 시 `Base.metadata.create_all()` 실행.  
> schema.sql 이후 실행되므로 테이블이 이미 존재하면 skip.

---

## 보안 정책

| 항목 | 정책 |
|---|---|
| 비밀번호 저장 | bcrypt 해시만 저장, 평문 금지 |
| 비밀번호 최소 길이 | 8자 이상 (Pydantic 검증) |
| 로그인 실패 메시지 | 이메일/비밀번호 구분 없이 동일 메시지 |
| Access Token 만료 | `401 "Token expired"` |
| 토큰 타입 혼용 | `401 "Invalid token type"` |
| Refresh Token 불일치 | `401 "Invalid refresh token"` |
| 비활성 계정 | `403 Forbidden` |
| JWT_SECRET | 환경변수로만 관리, 코드 하드코딩 절대 금지 |

---

## K8s 운영 설계

### DB 연결 재시도

```
최대 10회 × 5초 간격 재시도
→ 성공: 정상 기동
→ 10회 모두 실패: RuntimeError → K8s restartPolicy 로 재기동
```

`asyncio.run_in_executor` 로 blocking DB init을 thread pool에서 실행  
→ 이벤트 루프 블로킹 없음

### K8s Probe 설정 예시

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

---

## docker-compose (단독 실행)

`services/auth-service/docker-compose.yml` — db + redis + auth-service 3개 컨테이너 구성.

```
포트 매핑:
  auth-service : 8000:8000
  db           : 5432:5432
  redis        : 6379:6379

볼륨:
  auth_pgdata    (PostgreSQL 데이터)
  auth_redisdata (Redis 데이터)

플랫폼: linux/amd64 고정
```

---

## MSA 전체 연동 시 포트 매핑

MSA docker-compose(`docker-compose.msa.yml`)에서 auth-service는 외부 8001로 노출된다.

```
외부 8001 → 컨테이너 8000
```

다른 서비스에서 토큰 검증 시 동일한 JWT_SECRET 값을 `JWT_SECRET_KEY` 환경변수로 공유한다.

---

## curl 테스트

```bash
BASE=http://localhost:8000

# 회원가입
curl -s -X POST $BASE/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"테스트","email":"test@test.com","password":"Test1234!","phone":"010-0000-0000"}' | jq

# 로그인
curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"Test1234!"}' | jq

# 내 정보 (ACCESS_TOKEN 교체)
curl -s $BASE/auth/me \
  -H "Authorization: Bearer {ACCESS_TOKEN}" | jq

# 토큰 갱신 (REFRESH_TOKEN 교체)
curl -s -X POST $BASE/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"{REFRESH_TOKEN}"}' | jq

# 로그아웃
curl -s -X POST $BASE/auth/logout \
  -H "Authorization: Bearer {ACCESS_TOKEN}" | jq

# 헬스체크
curl -s $BASE/health | jq
```
