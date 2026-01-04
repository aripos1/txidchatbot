#!/bin/bash

# Docker Compose를 사용한 애플리케이션 시작
cd /var/www/multi_chain_tx_lookup

# certbot 서비스 제외하고 먼저 시작 (certbot은 인증서가 있는 경우만 작동)
docker-compose up -d web wordpress db nginx

# 시작 상태 확인
sleep 10
if docker-compose ps | grep -q "Up"; then
    echo "Application containers started successfully"
else
    echo "Application failed to start"
    docker-compose ps
    exit 1
fi

# 헬스체크
for i in {1..30}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "Health check passed"
        # certbot 서비스 시작 (SSL 인증서 자동 갱신)
        docker-compose up -d certbot
        exit 0
    fi
    echo "Health check attempt $i failed, retrying..."
    sleep 2
done

echo "Health check failed after 30 attempts"
exit 1 