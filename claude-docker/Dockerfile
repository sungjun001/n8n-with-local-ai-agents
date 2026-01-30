FROM node:20-bullseye-slim

WORKDIR /app

# 빌드 시점에 입력받을 변수 정의 (기본값 설정)
ARG SSH_USER=claudeuser
ARG SSH_PASS=1234

# 런타임(Entrypoint)에서도 사용할 수 있도록 환경변수로 저장
ENV SSH_USER_NAME=${SSH_USER}

# 1. 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    python3 \
    git \
    curl \
    bash \
    openssh-server \
    nano \
    sudo \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 2. 유저 생성 및 sudo 권한 부여 (비밀번호 없이 sudo 사용 가능하게 설정)
RUN groupadd -r ${SSH_USER} && \
    useradd -r -g ${SSH_USER} -m -s /bin/bash ${SSH_USER} && \
    echo "${SSH_USER}:${SSH_PASS}" | chpasswd && \
    usermod -aG sudo ${SSH_USER} && \
    echo "${SSH_USER} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# 3. SSH 설정
RUN mkdir /var/run/sshd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config

# 4. [핵심] NPM 패키지 시스템 전체 설치 (Root 권한으로 설치)
# 이렇게 하면 /usr/local/bin 에 설치되어 모든 유저가 경로 설정 없이 사용 가능
RUN npm install -g @anthropic-ai/claude-code @google/gemini-cli @openai/codex aws-s3-mcp

# 4.5 MinIO Client (mc) 설치 (CLI fallback용)
RUN curl https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc && \
    chmod +x /usr/local/bin/mc

# 5. UI 깨짐 방지용 터미널 설정
ENV TERM=xterm-256color

# 6. 엔트리포인트 스크립트 복사 및 실행 권한 부여
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# 7. 포트 개방
EXPOSE 22

# 8. [중요] 엔트리포인트 설정
# 컨테이너가 켜질 때마다 docker-entrypoint.sh가 먼저 실행되어 권한을 고침
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["/usr/sbin/sshd", "-D"]
