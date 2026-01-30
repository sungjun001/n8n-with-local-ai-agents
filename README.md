# n8n with Local AI Agents (Dockerized)

[한국어 설명 (Korean)](./README_KO.md) | [English](./README.md)

A complete, self-hosted framework for building AI automation workflows securely on your local infrastructure.

This project integrates **n8n** (Automation) with **Local AI Agents** (Gemini CLI, Claude) running in isolated Docker containers, connected via **MinIO** (S3-compatible storage) for artifact handling and **Nginx/Traefik** for secure reverse proxying.

## 🚀 Key Features

*   **Self-Hosted Automation**: Full n8n instance running locally with Docker.
*   **Sandboxed AI Agents**: AI agents (Gemini CLI) run in isolated containers (`claude-server`) with controlled access.
*   **Local Artifact Storage**: MinIO integration allows agents to generate and store files (images, code) locally with S3-compatible URLs.
*   **Secure Networking**: Network isolation separates the AI execution environment from the public web, connected only via specific bridges.
*   **Proxy Options**: Ready-to-use configurations for **Nginx** (Simple) or **Traefik** (Advanced).

## 📂 Project Structure

*   **`n8n-v2/`**: Docker configuration for the n8n automation server.
*   **`claude-docker/`**: The core AI Agent container.
    *   Includes `docker-entrypoint.sh` for dynamic configuration (MinIO alias, MCP server).
    *   Pre-configured with `aws-s3-mcp` for storage operations.
*   **`minio-storage/`**: (Optional) Self-hosted MinIO object storage.
*   **`nginx-proxy/`**: (Option A) Simple Nginx reverse proxy Setup.
*   **`traefik-proxy/`**: (Option B) Advanced Traefik reverse proxy Setup.

## 🛠️ Prerequisites

*   Docker & Docker Compose
*   A domain name (optional, but recommended for local DNS or generic placeholders like `s3.yourdomain.com`).

## ⚡ Getting Started

### 1. Network Setup
Create the required external networks:
```bash
docker network create n8n-v2-network
docker network create web
```

### 2. Reverse Proxy Setup (Choose One)
**Option A: Nginx (Recommended)**
```bash
cd nginx-proxy
cp .env.example .env  # Set your email
docker-compose up -d
```

**Option B: Traefik**
```bash
cd traefik-proxy
cp .env.example .env
docker-compose up -d
```

### 3. Start MinIO Storage (Optional)
If you don't have an external S3 provider, run this local instance.
```bash
cd minio-storage
cp .env.example .env
docker-compose up -d
```

### 4. Start AI Agent Infrastructure
```bash
cd claude-docker
cp .env.example .env
# Edit .env with your specific configuration (API Keys, MinIO Credentials)
docker-compose up -d
```

### 4. Start n8n
```bash
cd n8n-v2
docker-compose up -d
```

## 🤖 Usage Guide for Agents (Gemini CLI)

The `claude-server` container is pre-configured to use MinIO.
- **Auto-Config**: `docker-entrypoint.sh` sets up the `aws-s3-mcp` server.
- **Output Format**: Agents are instructed to strictly output JSON for file operations, enabling easy parsing in n8n.

**Example Request:**
> "Generate a cyberpunk city image and upload it to the bucket."

**Agent Response (JSON):**
```json
{
  "local_path": "/workspace/city.png",
  "s3_url": "https://s3.yourdomain.com/images/city.png"
}
```

## 📝 License
MIT