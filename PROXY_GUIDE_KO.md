# 리버스 프록시 설정 가이드 (Reverse Proxy Configuration)

이 프로젝트는 **Nginx** (기본값)와 **Traefik** 두 가지 리버스 프록시 구성을 지원합니다.
각 서비스(`n8n`, `minio-storage`)의 설정 파일에는 두 가지 옵션이 모두 준비되어 있어 쉽게 전환할 수 있습니다.

## 1. 환경 변수 설정 (Environment Variables)
컨테이너를 실행하기 전, 각 `.env` 파일에 도메인이 올바르게 설정되어 있는지 확인하세요.

### `nginx-proxy/.env` (또는 `traefik-proxy/.env`)
```bash
DEFAULT_EMAIL=user@example.com
```

### 서비스별 `.env` 파일
- **n8n (`n8n-v2/.env`)**:
  ```bash
  DOMAIN=n8n.yourdomain.com
  ```
- **MinIO (`claude-docker/.env` 및 `minio-storage/.env`)**:
  ```bash
  MINIO_ENDPOINT=s3.yourdomain.com
  ```

---

## 2. 옵션 A: Nginx (기본값 - Default)

`docker-compose.yml` 파일들은 기본적으로 환경 변수 기반의 Nginx 설정을 사용하도록 되어 있습니다.

**작동 원리**:
- `VIRTUAL_HOST`: Nginx에게 어떤 도메인을 라우팅할지 알려줍니다.
- `LETSENCRYPT_HOST`: 해당 도메인에 대한 SSL 인증서를 자동 발급받습니다.

**사용법**:
별도의 파일 수정 없이 `nginx-proxy`와 서비스들을 실행하면 즉시 작동합니다.

---

## 3. 옵션 B: Traefik (고급 - Advanced)

Traefik을 사용하고 싶다면(예: MinIO API `9000`와 Console `9001`을 각각 다른 도메인으로 연결 등), 아래 절차를 따르세요.

**1단계. Traefik 실행**
```bash
# Nginx가 켜져 있다면 끕니다
cd nginx-proxy
docker-compose down

# Traefik 실행
cd ../traefik-proxy
docker-compose up -d
```

**2단계. Traefik 레이블 활성화**
각 `docker-compose.yml` 파일(`n8n-v2/docker-compose.local.yml`, `minio-storage/docker-compose.yml`)을 열어 수정합니다:

1.  **Nginx 환경 변수 주석 처리**:
    ```yaml
    environment:
      # - VIRTUAL_HOST=...
      # - LETSENCRYPT_HOST=...
    ```

2.  **Traefik 레이블 주석 해제 및 활성화**:
    ```yaml
    labels:
      - "traefik.enable=true"  # Traefik 사용 시에만 반드시 true로 변경 (중요!)
      - "traefik.http.routers.service-name.rule=Host(...)"
      ...
    ```
    > ⚠️ **주의**: 기본값은 충돌 방지를 위해 `false`로 되어 있습니다. Traefik이 이 컨테이너를 인식하게 하려면 반드시 `true`로 바꿔야 합니다.

3.  **서비스 재시작**:
    ```bash
    docker-compose up -d --force-recreate
    ```
