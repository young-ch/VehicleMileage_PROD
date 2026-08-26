#!/bin/bash
echo "1/2: 기존 도커 서비스들 멈추고 삭제하는 중..."
docker-compose down

echo "2/2: 웹과 DB 최신 코드로 빌드 및 실행하는 중..."
docker-compose up -d --build

echo "✅ 웹사이트(8885포트)와 DB(3306포트)가 모두 실행되었습니다!"
