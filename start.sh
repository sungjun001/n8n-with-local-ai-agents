#!/bin/bash

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Claude API Services...${NC}"

# 1. 네트워크 생성 (이미 존재하면 무시됨)
echo -e "${GREEN}🌐 Checking Docker networks...${NC}"
docker network create web 2>/dev/null || true
docker network create n8n-v2-network 2>/dev/null || true

# 2. Nginx Proxy 실행
echo -e "${GREEN}Starting Nginx Proxy...${NC}"
cd nginx-proxy
docker-compose up -d
cd ..

# 3. n8n 실행
echo -e "${GREEN}Starting n8n Services...${NC}"
cd n8n-v2
docker-compose up -d
cd ..

# 4. Claude Server & Monitor 실행
echo -e "${GREEN}Starting Claude Server & Monitor...${NC}"
cd claude-docker
docker-compose up -d
cd ..

echo -e "${BLUE}✨ All services started successfully!${NC}"
