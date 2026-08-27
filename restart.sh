#!/bin/bash
echo "1/3: 기존 도커 서비스 및 컨테이너 삭제 중..."
docker rm -f smu-jira-app smu-jira-db 2>/dev/null || true
docker-compose down --remove-orphans 2>/dev/null || true

echo "2/3: 웹과 DB 최신 코드로 빌드 및 실행하는 중..."
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    docker compose up -d --build
else
    docker-compose up -d --build
fi

echo "✅ 웹사이트(8885포트)와 DB(3306포트)가 성공적으로 실행되었습니다!"
