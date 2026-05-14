# GHCR 사용 가이드

GitHub Container Registry(GHCR)에 도커 이미지를 올리고 내려받는 방법 정리.

---

## 이 프로젝트 이미지 주소

```
ghcr.io/gummy-jelly/stays/{서비스명}:latest
```

| 서비스 | 이미지 주소 |
|---|---|
| auth-service | `ghcr.io/gummy-jelly/stays/auth-service:latest` |
| stays-service | `ghcr.io/gummy-jelly/stays/stays-service:latest` |
| event-service | `ghcr.io/gummy-jelly/stays/event-service:latest` |
| coupon-service | `ghcr.io/gummy-jelly/stays/coupon-service:latest` |
| booking-service | `ghcr.io/gummy-jelly/stays/booking-service:latest` |
| notification-service | `ghcr.io/gummy-jelly/stays/notification-service:latest` |
| api-gateway | `ghcr.io/gummy-jelly/stays/api-gateway:latest` |

---

## 1단계 — PAT 발급 (최초 1회)

GHCR은 GitHub 계정 비밀번호 대신 **PAT(Personal Access Token)**으로 로그인한다.

1. GitHub 접속 → 우상단 프로필 클릭
2. **Settings** 클릭
3. 왼쪽 맨 아래 **Developer settings** 클릭
4. **Personal access tokens → Tokens (classic)** 클릭
5. **Generate new token (classic)** 클릭
6. Note(이름)에 아무거나 입력 (예: `ghcr-token`)
7. 아래 권한 체크:
   - ✅ `write:packages`
   - ✅ `read:packages`
   - ✅ `delete:packages` (삭제할 일 있으면)
8. **Generate token** 클릭
9. 발급된 토큰 복사 (`ghp_xxxxx...`) → **다시 볼 수 없으니 반드시 저장**

---

## 2단계 — 로그인

```bash
echo "발급받은_토큰" | docker login ghcr.io -u GitHub계정명 --password-stdin
```

**이 프로젝트 예시**
```bash
echo "ghp_xxxxx..." | docker login ghcr.io -u gummy-jelly --password-stdin
```

성공하면:
```
Login Succeeded
```

> 한 번 로그인하면 `~/.docker/config.json`에 저장돼서 다음부터는 안 해도 된다.

---

## 3단계 — 빌드 & 푸시

### 기본 구조

```bash
# 빌드
docker buildx build \
  --platform linux/amd64 \
  --label "org.opencontainers.image.source=https://github.com/gummy-jelly/stays" \
  --push \
  -t ghcr.io/gummy-jelly/stays/서비스명:latest \
  ./services/서비스명/
```

### 서비스별 명령어

```bash
# auth-service
docker buildx build --platform linux/amd64 --push \
  -t ghcr.io/gummy-jelly/stays/auth-service:latest \
  ./services/auth-service/

# stays-service
docker buildx build --platform linux/amd64 --push \
  -t ghcr.io/gummy-jelly/stays/stays-service:latest \
  ./services/stays-service/

# event-service
docker buildx build --platform linux/amd64 --push \
  -t ghcr.io/gummy-jelly/stays/event-service:latest \
  ./services/event-service/

# coupon-service
docker buildx build --platform linux/amd64 --push \
  -t ghcr.io/gummy-jelly/stays/coupon-service:latest \
  ./services/coupon-service/

# booking-service
docker buildx build --platform linux/amd64 --push \
  -t ghcr.io/gummy-jelly/stays/booking-service:latest \
  ./services/booking-service/

# notification-service
docker buildx build --platform linux/amd64 --push \
  -t ghcr.io/gummy-jelly/stays/notification-service:latest \
  ./services/notification-service/

# api-gateway
docker buildx build --platform linux/amd64 --push \
  -t ghcr.io/gummy-jelly/stays/api-gateway:latest \
  ./services/api-gateway/
```

### 전체 한 번에 빌드·푸시하는 스크립트

```bash
#!/bin/bash
REGISTRY="ghcr.io/gummy-jelly/stays"
LABEL="org.opencontainers.image.source=https://github.com/gummy-jelly/stays"
SERVICES="auth-service stays-service event-service coupon-service booking-service notification-service api-gateway"

for svc in $SERVICES; do
  echo ">>> $svc 빌드 중..."
  docker buildx build \
    --platform linux/amd64 \
    --label "$LABEL" \
    --push \
    -t $REGISTRY/$svc:latest \
    ./services/$svc/
  echo ">>> $svc 완료"
done
```

---

## 4단계 — 패키지 Public으로 변경

> 기본값이 **Private**이다. K8s 클러스터에서 로그인 없이 pull 하려면 **Public**으로 바꿔야 한다.

1. `https://github.com/gummy-jelly?tab=packages` 접속
2. 패키지 목록에서 변경할 서비스 클릭 (예: `stays/auth-service`)
3. 오른쪽 **Package settings** 클릭
4. 맨 아래 **Danger Zone** 섹션
5. **Change visibility** 클릭 → **Public** 선택
6. 패키지 이름 입력 후 확인

**7개 서비스 전부 반복** (auth / stays / event / coupon / booking / notification / api-gateway)

---

## 5단계 — Pull (내려받기)

### Public 이미지 (로그인 없이 가능)
```bash
docker pull ghcr.io/gummy-jelly/stays/auth-service:latest
```

### Private 이미지 (로그인 필요)
```bash
# 먼저 로그인
echo "토큰" | docker login ghcr.io -u gummy-jelly --password-stdin

# pull
docker pull ghcr.io/gummy-jelly/stays/auth-service:latest
```

### K8s 클러스터에서 pull

Public이면 별도 설정 없이 바로 사용 가능:
```yaml
# k8s manifest 예시
containers:
  - name: auth-service
    image: ghcr.io/gummy-jelly/stays/auth-service:latest
```

Private이면 imagePullSecret 설정 필요:
```bash
# K8s에 GHCR 인증 시크릿 등록
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=gummy-jelly \
  --docker-password=토큰 \
  --namespace=default
```
```yaml
# manifest에 추가
spec:
  imagePullSecrets:
    - name: ghcr-secret
  containers:
    - name: auth-service
      image: ghcr.io/gummy-jelly/stays/auth-service:latest
```

---

## docker-compose에서 사용

이 프로젝트는 `docker-compose.msa.yml`에 GHCR 이미지가 이미 설정되어 있다.

```bash
# 최신 이미지 pull
docker compose -f docker-compose.msa.yml pull

# 실행
docker compose -f docker-compose.msa.yml up

# Public이 아니라면 먼저 로그인 후 pull
echo "토큰" | docker login ghcr.io -u gummy-jelly --password-stdin
docker compose -f docker-compose.msa.yml pull
```

---

## 이미지 목록 확인

```bash
# 로컬에 받아진 이미지 확인
docker images | grep ghcr.io/gummy-jelly

# GHCR에 올라간 패키지 확인 (웹)
# https://github.com/gummy-jelly?tab=packages
```

---

## 이미지 삭제

### 로컬에서만 삭제
```bash
docker rmi ghcr.io/gummy-jelly/stays/auth-service:latest
```

### GHCR에서 삭제
1. `https://github.com/gummy-jelly?tab=packages` 접속
2. 삭제할 패키지 클릭
3. 오른쪽 **Package settings** → **Danger Zone** → **Delete this package**

---

## 자주 쓰는 명령어 요약

```bash
# 로그인
echo "토큰" | docker login ghcr.io -u gummy-jelly --password-stdin

# 빌드 + 푸시 (amd64)
docker buildx build --platform linux/amd64 --push \
  -t ghcr.io/gummy-jelly/stays/서비스명:latest \
  ./services/서비스명/

# pull
docker pull ghcr.io/gummy-jelly/stays/서비스명:latest

# 로컬 이미지 목록
docker images | grep ghcr

# 로그아웃
docker logout ghcr.io
```

---

## buildx 관련 (M1/M2 Mac에서 amd64 빌드할 때)

```bash
# builder 생성 (최초 1회)
docker buildx create --name amd64-builder --driver docker-container --use

# builder 확인
docker buildx ls

# builder 삭제
docker buildx rm amd64-builder
```

> `--platform linux/amd64` 를 붙이는 이유:  
> M1/M2 Mac은 기본 아키텍처가 `arm64`라서 그냥 빌드하면 kubeadm VM(x86_64)·EKS(x86_64)에서 동작 안 함.
