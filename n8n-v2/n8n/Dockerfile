# 최신 버전 사용
#FROM docker.n8n.io/n8nio/n8n:1.123.4
FROM docker.n8n.io/n8nio/n8n:2.4.5


COPY --from=alpine:3.23 /sbin/apk /sbin/apk
COPY --from=alpine:3.23 /usr/lib/libapk.so* /usr/lib/

USER root

# 1. 라이브러리들을 전역(-g)으로 설치합니다.
# 이렇게 해야 볼륨 마운트(데이터 저장소 연결) 시 파일이 가려지지 않습니다.
RUN npm install -g \
    axios \
    cheerio \
    pdf-parse \
    moment \
    lodash \
    openai \
    qdrant-client \
    js-yaml \
    dotenv

RUN apk add --no-cache ffmpeg curl yt-dlp

# node 유저로 전환
USER node

# n8n 커스텀 노드 디렉토리 생성
RUN mkdir -p /home/node/.n8n/custom

# 커스텀 노드 디렉토리에서 패키지 설치
WORKDIR /home/node/.n8n/custom


# 작업 디렉토리를 다시 홈으로 변경
WORKDIR /home/node

