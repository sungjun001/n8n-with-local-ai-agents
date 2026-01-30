# Reverse Proxy Configuration Guide

This project supports two Reverse Proxy configurations: **Nginx** (Default) and **Traefik**.
Each service (`n8n`, `minio-storage`) is pre-configured with settings for both, allowing you to switch easily.

## 1. Environment Variables
Before running any containers, ensure your `.env` files have the correct domains.

### `nginx-proxy/.env` (or `traefik-proxy/.env`)
```bash
DEFAULT_EMAIL=user@example.com
```

### Service `.env` Files
- **n8n (`n8n-v2/.env`)**:
  ```bash
  DOMAIN=n8n.yourdomain.com
  ```
- **MinIO (`claude-docker/.env` & `minio-storage/.env`)**:
  ```bash
  MINIO_ENDPOINT=s3.yourdomain.com
  ```

---

## 2. Option A: Nginx (Default)

The `docker-compose.yml` files are set up for Nginx by default using environment variables.

**How it works:**
- `VIRTUAL_HOST`: Tells Nginx which domain to route.
- `LETSENCRYPT_HOST`: Requests an SSL certificate for that domain.

**To use:**
Simply start the `nginx-proxy` and your services. No file changes needed.

---

## 3. Option B: Traefik (Advanced)

If you prefer Traefik (e.g., for routing multiple ports like MinIO API `9000` + Console `9001`), follow these steps.

**Step 1. Start Traefik**
```bash
docker stop nginx-proxy
cd ../traefik-proxy
docker-compose up -d
```

**Step 2. Enable Traefik Labels**
In each `docker-compose.yml` (`n8n-v2/docker-compose.local.yml`, `minio-storage/docker-compose.yml`):

1.  **Comment out** the Nginx Environment variables:
    ```yaml
    environment:
      # - VIRTUAL_HOST=...
      # - LETSENCRYPT_HOST=...
    ```

2.  **Uncomment and Enable** the Traefik Labels:
    ```yaml
    labels:
      - "traefik.enable=true"  # Change to true ONLY if using Traefik (Important!)
      - "traefik.http.routers.service-name.rule=Host(...)"
      ...
    ```
    > ⚠️ **Note**: The default value is `false` to prevent conflicts. You **must** change it to `true` for Traefik to detect the container.

3.  **Restart the service**:
    ```bash
    docker-compose up -d --force-recreate
    ```
