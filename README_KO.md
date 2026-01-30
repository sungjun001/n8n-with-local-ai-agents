# n8n with Local AI Agents (Dockerized)

[English](./README.md) | [한국어 설명 (Korean)](./README_KO.md)

로컬 인프라에서 안전하게 AI 자동화 워크플로우를 구축하기 위한 완전한 셀프 호스팅 프레임워크입니다.

이 프로젝트는 **n8n** (자동화 도구)을 격리된 Docker 컨테이너에서 실행되는 **로컬 AI 에이전트** (Gemini CLI, Claude)와 통합합니다. 생성된 파일(이미지, 코드 등)은 **MinIO** (S3 호환 스토리지)를 통해 관리되며, **Nginx/Traefik**을 통해 안전하게 리버스 프록시 처리됩니다.

## 🚀 주요 기능

*   **셀프 호스팅 자동화**: Docker를 사용하여 로컬에서 완벽하게 실행되는 n8n 인스턴스.
*   **샌드박스 AI 에이전트**: AI 에이전트(Gemini CLI)가 격리된 컨테이너(`claude-server`) 내에서 제어된 권한으로 실행됩니다.
*   **로컬 아티팩트 저장소**: MinIO 통합을 통해 에이전트가 파일을 생성하고 로컬에 저장하며, S3 호환 URL을 제공합니다.
*   **안전한 네트워킹**: 네트워크 격리를 통해 AI 실행 환경을 외부 웹과 분리하고, 특정 브릿지를 통해서만 연결합니다.
*   **프록시 옵션 제공**: **Nginx** (간편함) 또는 **Traefik** (고급 기능) 중 선택하여 사용할 수 있는 설정 파일 제공.

## 📂 프로젝트 구조

*   **`n8n-v2/`**: n8n 자동화 서버를 위한 Docker 구성.
*   **`claude-docker/`**: 핵심 AI 에이전트 컨테이너.
    *   `docker-entrypoint.sh`를 포함하여 동적 구성(MinIO 별칭, MCP 서버)을 지원합니다.
    *   스토리지 작업을 위해 `aws-s3-mcp`가 사전 구성되어 있습니다.
*   **`minio-storage/`**: (선택 사항) 셀프 호스팅 MinIO 오브젝트 스토리지.
*   **`nginx-proxy/`**: (옵션 A) 간편한 Nginx 리버스 프록시 설정.
*   **`traefik-proxy/`**: (옵션 B) 고급 Traefik 리버스 프록시 설정.

## 🛠️ 사전 준비 사항

*   Docker & Docker Compose
*   도메인 이름 (선택 사항이지만, 로컬 DNS나 `s3.yourdomain.com` 같은 일반적인 플레이스홀더 사용 권장).

## ⚡ 시작하기 (Getting Started)

### 1. 네트워크 설정
필요한 외부 네트워크를 먼저 생성합니다:
```bash
docker network create n8n-v2-network
docker network create web
```

### 2. 리버스 프록시 설정 (택 1)
**옵션 A: Nginx (추천 - 간편함)**
```bash
cd nginx-proxy
cp .env.example .env  # 이메일 설정 필요
docker-compose up -d
```

**옵션 B: Traefik**
```bash
cd traefik-proxy
cp .env.example .env
docker-compose up -d
```

### 3. MinIO 스토리지 시작 (선택 사항)
외부 S3 제공자가 없다면 이 로컬 인스턴스를 실행하세요.
```bash
cd minio-storage
cp .env.example .env
docker-compose up -d
```

### 4. AI 에이전트 인프라 시작
```bash
cd claude-docker
cp .env.example .env
# .env 파일을 열어 API Key, MinIO 자격 증명 등을 설정하세요.
docker-compose up -d
```

### 4. n8n 시작
```bash
cd n8n-v2
docker-compose up -d
```

## 🤖 에이전트 사용 가이드 (Gemini CLI)

`claude-server` 컨테이너는 MinIO를 사용하도록 사전 설정되어 있습니다.
- **자동 구성**: `docker-entrypoint.sh` 스크립트가 `aws-s3-mcp` 서버를 자동으로 설정합니다.
- **출력 형식**: 에이전트는 파일 작업 시 n8n에서 쉽게 파싱할 수 있도록 **엄격한 JSON 형식**으로 출력하도록 지시받습니다.

**요청 예시:**
> "사이버펑크 도시 이미지를 생성해서 버킷에 업로드해줘."

**에이전트 응답 (JSON):**
```json
{
  "local_path": "/workspace/city.png",
  "s3_url": "https://s3.yourdomain.com/images/city.png"
}
```

## 📝 라이선스
MIT
