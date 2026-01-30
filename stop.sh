#!/bin/bash

# 색상 정의
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${RED}🛑 Stopping Claude API Services...${NC}"

# 1. Claude Server & Monitor 종료
echo -e "${RED}Stopping Claude Server & Monitor...${NC}"
cd claude-docker
docker-compose down
cd ..

# 2. n8n 종료
echo -e "${RED}Stopping n8n Services...${NC}"
cd n8n-v2
docker-compose down
cd ..

# 3. Nginx Proxy 종료
echo -e "${RED}Stopping Nginx Proxy...${NC}"
cd nginx-proxy
docker-compose down
cd ..

echo -e "${RED}✨ All services stopped.${NC}"
