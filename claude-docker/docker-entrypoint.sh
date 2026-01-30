#!/bin/bash
set -e

USER_NAME=${SSH_USER_NAME:-claudeuser}
echo "🔧 Fixing permissions for user: $USER_NAME..."

chown -R $USER_NAME:$USER_NAME /home/$USER_NAME

# /workspace 디렉토리 설정
echo "📁 Setting up /workspace directory..."
mkdir -p /workspace
chown $USER_NAME:$USER_NAME /workspace

# 시스템 전역 환경변수 설정
echo "🔑 Setting up environment variables..."
{
    grep -v "GEMINI_API_KEY\|ANTHROPIC_BASE_URL\|MINIO_\|AWS_" /etc/environment 2>/dev/null || true
    [ -n "$NANOBANANA_GEMINI_API_KEY" ] && echo "GEMINI_API_KEY=\"$NANOBANANA_GEMINI_API_KEY\""
    [ -n "$ANTHROPIC_BASE_URL" ] && echo "ANTHROPIC_BASE_URL=\"$ANTHROPIC_BASE_URL\""
    [ -n "$MINIO_ACCESS_KEY" ] && echo "AWS_ACCESS_KEY_ID=\"$MINIO_ACCESS_KEY\""
    [ -n "$MINIO_SECRET_KEY" ] && echo "AWS_SECRET_ACCESS_KEY=\"$MINIO_SECRET_KEY\""
    [ -n "$MINIO_BUCKET" ] && echo "MINIO_BUCKET=\"$MINIO_BUCKET\""
    # MINIO_ENDPOINT가 있으면 사용하고 없으면 기본값 사용
    ENDPOINT="${MINIO_ENDPOINT:-s3.yourdomain.com}"
    echo "AWS_ENDPOINT_URL=\"https://$ENDPOINT\""
    echo "MINIO_ENDPOINT=\"$ENDPOINT\""
} > /tmp/environment && mv /tmp/environment /etc/environment

# .bashrc 설정
BASHRC="/home/$USER_NAME/.bashrc"
cat > "$BASHRC" << 'EOF'
# Source global definitions
if [ -f /etc/bashrc ]; then
    . /etc/bashrc
fi

# Load environment variables
set -a
[ -f /etc/environment ] && . /etc/environment
set +a

# Change to workspace directory
cd /workspace 2>/dev/null || true
EOF
chown $USER_NAME:$USER_NAME "$BASHRC"

# ✅ [Agent Context] 작업 공간에 에이전트를 위한 안내 파일 생성
# GEMINI.md로 저장하면 Agent가 시작할 때 자동으로 읽어들입니다.
CONTEXT_FILE="/workspace/GEMINI.md"
cat > "$CONTEXT_FILE" << EOF
# Environment Context for Agent

## Available Tools & Configuration

### 1. Object Storage (MinIO)
- **Primary Method**: Use the MCP Server \`aws-s3-mcp\` (configured in \`~/.gemini/settings.json\`).
- **Fallback Method**: Use shell command \`mc\` (MinIO Client).
    - Status: \`mc\` is installed and the alias **\`myminio\`** (or \`minio\`) is PRE-CONFIGURED.
    - **IMPORTANT**: Do NOT try to read \`~/.bashrc\` or \`~/.mc/config.json\`. Just run the command.
    - Example: \`mc cp /workspace/file.png myminio/${MINIO_BUCKET:-images}/\`
    - Endpoint: https://${MINIO_ENDPOINT:-s3.yourdomain.com}

### 2. File System
- Current working directory: \`/workspace\`
- **Constraint**: You are sandboxed to \`/workspace\`. Do not try to read files in \`~\` or \`/home/claudeuser\`.

### 3. OUTPUT FORMAT PROTOCOL
**CASE A: File/Image Generation (Strict JSON)**
- If you have generated, edited, or uploaded files:
  - You **MUST** return a **RAW JSON BLOCK** so the system can process the URLs.
  - **NO** conversational filler.
  - Structure:
    \`\`\`json
    {
      "local_path": "/workspace/file.png",
      "s3_url": "https://${MINIO_ENDPOINT:-s3.yourdomain.com}/${MINIO_BUCKET:-images}/file.png"
    }
    \`\`\`

**CASE B: General Conversation (Flexible)**
- If the user asks a question, requests code, or asks for a specific format (Markdown, HTML, etc.):
  - **IGNORE** the system instruction about \`format_final_json_response\`.
  - Respond naturally in the format the user requested.
  - Do NOT wrap text in JSON unless explicitly asked.
EOF
chown $USER_NAME:$USER_NAME "$CONTEXT_FILE"


# .profile 설정
PROFILE="/home/$USER_NAME/.profile"
cat > "$PROFILE" << 'EOF'
set -a
[ -f /etc/environment ] && . /etc/environment
set +a
[ -f ~/.bashrc ] && . ~/.bashrc
EOF
chown $USER_NAME:$USER_NAME "$PROFILE"

# Gemini MCP 설정 (MinIO)
echo "🔧 Configuring Gemini MCP..."
GEMINI_DIR="/home/$USER_NAME/.gemini"
mkdir -p "$GEMINI_DIR"

cat > "$GEMINI_DIR/settings.json" << EOF
{
  "mcpServers": {
    "minio": {
      "command": "npx",
      "args": ["aws-s3-mcp"],
      "env": {
        "AWS_ACCESS_KEY_ID": "${MINIO_ACCESS_KEY}",
        "AWS_SECRET_ACCESS_KEY": "${MINIO_SECRET_KEY}",
        "AWS_REGION": "us-east-1",
        "AWS_ENDPOINT_URL": "https://${MINIO_ENDPOINT:-s3.yourdomain.com}",
        "S3_BUCKETS": "${MINIO_BUCKET:-images}"
      }
    }
  }
}
EOF

chown -R $USER_NAME:$USER_NAME "$GEMINI_DIR"
echo "✅ Gemini MCP configured"

# MinIO Client (mc) 설정
if command -v mc >/dev/null 2>&1; then
    echo "🔧 Configuring MinIO Client (mc)..."
    # mc alias 설정 (myminio)
    # MINIO_ACCESS_KEY 확인을 위해 디버그 로그 출력
    if [ -z "$MINIO_ACCESS_KEY" ] || [ -z "$MINIO_SECRET_KEY" ]; then
        echo "⚠️  WARNING: MINIO_ACCESS_KEY or MINIO_SECRET_KEY is missing via env vars. 'myminio' alias cannot be set."
    else
        TARGET_ENDPOINT="https://${MINIO_ENDPOINT:-s3.yourdomain.com}"
        echo "🔧 Setting 'myminio' alias to $TARGET_ENDPOINT..."
        echo "   Access Key: $MINIO_ACCESS_KEY"
        
        # [Fix] 특수문자($ 등)가 포함된 비밀번호가 su -c 쉘 해석 과정에서 변질되지 않도록 escaping 처리
        SAFE_ENDPOINT=$(printf %q "$TARGET_ENDPOINT")
        SAFE_ACCESS=$(printf %q "$MINIO_ACCESS_KEY")
        SAFE_SECRET=$(printf %q "$MINIO_SECRET_KEY")

        # su - claudeuser -c "mc alias set ..." 실행
        if su - $USER_NAME -c "mc alias set myminio $SAFE_ENDPOINT $SAFE_ACCESS $SAFE_SECRET"; then
             echo "✅ MinIO Client configured as 'myminio' pointing to $TARGET_ENDPOINT"
             # 혹시 Agent가 'minio'라고 추측할 경우를 대비해 'minio'라는 이름으로도 하나 더 등록
             su - $USER_NAME -c "mc alias set minio $SAFE_ENDPOINT $SAFE_ACCESS $SAFE_SECRET" >/dev/null 2>&1 || true
             
             # [Auto-Setup] 버킷 생성 및 공개 읽기(download) 권한 설정
             BUCKET_NAME="${MINIO_BUCKET:-images}"
             echo "🔧 Ensuring bucket '$BUCKET_NAME' exists and is public..."
             su - $USER_NAME -c "mc mb myminio/$BUCKET_NAME" >/dev/null 2>&1 || true
             su - $USER_NAME -c "mc anonymous set download myminio/$BUCKET_NAME" >/dev/null 2>&1 || true
             echo "✅ Bucket '$BUCKET_NAME' is ready and public."
        else
             echo "❌ FAILED to configure 'myminio' alias. Please check your credentials."
        fi
    fi
fi

exec "$@"
