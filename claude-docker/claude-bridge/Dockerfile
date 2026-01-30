FROM python:3.9-slim

WORKDIR /app

# 1. 필수 시스템 패키지 설치 (sshpass, openssh-client)
RUN apt-get update && \
    apt-get install -y sshpass openssh-client && \
    rm -rf /var/lib/apt/lists/*

# 2. Python 라이브러리 설치
RUN pip install --no-cache-dir fastapi uvicorn pydantic

# 3. 소스 코드 복사
COPY ./src/main.py .

# 4. 서버 실행 (8000번 포트)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
