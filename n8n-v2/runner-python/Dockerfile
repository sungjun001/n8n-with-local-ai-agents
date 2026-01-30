# 문서 가이드에 따라 n8nio/runners 이미지 사용 (버전은 n8n 메인과 맞추거나 최신 사용)
FROM n8nio/runners:latest

USER root

RUN cd /opt/runners/task-runner-javascript && pnpm add moment lodash

# 1. Python 패키지 설치
# n8nio/runners 이미지는 내부적으로 'uv'를 사용하여 패키지를 관리합니다.
# /opt/runners/task-runner-python 경로에서 설치해야 인식됩니다.
RUN cd /opt/runners/task-runner-python && \
    uv pip install --system \
    requests \
    pandas \
    numpy \
    beautifulsoup4 \
    openai

# 2. 설정 파일 복사 (아래 2번 단계에서 만들 파일)
COPY n8n-task-runners.json /etc/n8n-task-runners.json

USER runner
