#!/bin/bash
# AWS EC2 배포 스크립트

set -e

echo "========================================="
echo "AWS EC2 배포 스크립트 시작"
echo "========================================="

# Docker 설치 확인 (Ubuntu/Debian)
if ! command -v docker &> /dev/null; then
    echo "Docker가 설치되어 있지 않습니다. 설치를 시작합니다..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "Docker 설치 완료. 로그아웃 후 다시 로그인하거나 'newgrp docker' 명령을 실행하세요."
    exit 1
fi

# Docker Compose 설치 확인 (v2 또는 v1)
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Docker Compose가 설치되어 있지 않습니다. 설치를 시작합니다..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
    echo "Docker Compose 설치 완료"
fi

# Docker Compose 명령어 확인 (v2 또는 v1)
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# .env 파일 확인
if [ ! -f .env ]; then
    echo "경고: .env 파일이 없습니다. 환경 변수를 설정해야 합니다."
    echo ".env 파일을 생성하고 필요한 환경 변수를 설정하세요."
    exit 1
fi

# Docker 서비스 시작
echo "Docker 서비스 시작..."
sudo systemctl start docker || sudo service docker start || true

# 기존 컨테이너 정리
echo "기존 컨테이너 정리..."
$DOCKER_COMPOSE down || true

# Docker 이미지 빌드 (프로덕션 Dockerfile 사용)
echo "Docker 이미지 빌드 시작..."
$DOCKER_COMPOSE build --no-cache

# 컨테이너 시작
echo "컨테이너 시작..."
$DOCKER_COMPOSE up -d

# 헬스체크 대기
echo "헬스체크 대기 중..."
sleep 10

# 헬스체크 확인
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ 헬스체크 성공!"
else
    echo "⚠️ 헬스체크 실패. 로그를 확인하세요."
    $DOCKER_COMPOSE logs --tail=50 web
fi

# 로그 확인
echo "========================================="
echo "배포 완료!"
echo "========================================="
echo "애플리케이션 URL: http://localhost:8000"
echo "헬스체크 URL: http://localhost:8000/health"
echo ""
echo "유용한 명령어:"
echo "  - 로그 확인: $DOCKER_COMPOSE logs -f web"
echo "  - 상태 확인: $DOCKER_COMPOSE ps"
echo "  - 컨테이너 재시작: $DOCKER_COMPOSE restart web"
echo "  - 컨테이너 중지: $DOCKER_COMPOSE down"
echo "========================================="

