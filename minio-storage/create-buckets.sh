#!/bin/sh
# MinIO가 완전히 뜰 때까지 잠시 대기
sleep 3

echo "🔧 Configuring MinIO..."
# 1. Alias 설정
/usr/bin/mc alias set myminio http://minio:9000 "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"

# 2. 버킷 생성 (이미 존재하면 무시됨)
echo "📁 Creating bucket: ${MINIO_BUCKET:-common}"
/usr/bin/mc mb myminio/"${MINIO_BUCKET:-common}" || true

# 3. 공개 권한 설정 (Download only)
echo "🔓 Setting anonymous policy to download"
/usr/bin/mc anonymous set download myminio/"${MINIO_BUCKET:-common}"

echo "✅ MinIO setup complete!"
exit 0
