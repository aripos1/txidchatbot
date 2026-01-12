# SSL 인증서 자동 갱신 가이드

## 개요
이 설정은 Let's Encrypt SSL 인증서를 자동으로 갱신합니다.

## 자동 갱신 작동 방식

### Docker Compose 환경 (권장)
- `certbot` 서비스가 12시간마다 인증서를 확인하고 갱신합니다
- 인증서가 만료되기 30일 전에 자동으로 갱신됩니다
- webroot 방식으로 작동하여 nginx를 중지하지 않고도 갱신 가능합니다

## 설정 방법

### 1. 서버에서 적용
```bash
cd /var/www/multi_chain_tx_lookup

# docker-compose 새로 빌드 및 시작
docker-compose down
docker-compose up -d

# certbot 서비스 상태 확인
docker-compose ps certbot
```

### 2. 현재 인증서 갱신 (수동)
```bash
# Docker Compose를 사용하는 경우
./scripts/ssl/renew_certificate.sh

# 또는 수동으로
docker-compose exec certbot certbot renew --webroot --webroot-path=/var/www/html --force-renewal
docker-compose restart nginx
```

## 파일 구조

### 주요 수정 파일
- `docker-compose.yml`: certbot 서비스 추가
- `wordpress/nginx/nginx.conf`: `.well-known` 경로 추가
- `scripts/ssl/renew_certificate.sh`: 수동 갱신 스크립트
- `scripts/deploy/after_install.sh`: 자동 갱신 설정

### certbot 서비스
```yaml
certbot:
  image: certbot/certbot:latest
  volumes:
    - /etc/letsencrypt:/etc/letsencrypt
    - certbot_data:/var/lib/letsencrypt
    - nginx_html:/var/www/html
  entrypoint: 자동 갱신 루프 (12시간마다)
```

## 동작 확인

### certbot 로그 확인
```bash
docker-compose logs certbot
```

### 인증서 만료일 확인
```bash
sudo certbot certificates
```

### 수동 갱신 테스트
```bash
docker-compose exec certbot certbot renew --webroot --webroot-path=/var/www/html --dry-run
```

## 문제 해결

### 인증서 갱신 실패 시
```bash
# certbot 컨테이너 재시작
docker-compose restart certbot

# 로그 확인
docker-compose logs -f certbot

# 수동 갱신 시도
docker-compose exec certbot certbot renew --webroot --webroot-path=/var/www/html --force-renewal
```

### nginx가 인증서를 읽지 못하는 경우
```bash
# nginx 컨테이너 재시작
docker-compose restart nginx

# 인증서 경로 확인
docker-compose exec nginx ls -la /etc/letsencrypt/live/txid.shop/
```

## 인증서 관리 스크립트

### 통합 관리 스크립트 (권장)
```bash
# 인증서 상태 확인
./scripts/ssl/ssl_manager.sh check

# 특정 도메인 확인
./scripts/ssl/ssl_manager.sh check example.com

# 인증서 갱신
./scripts/ssl/ssl_manager.sh renew
```

### 개별 스크립트 사용

#### 1. 인증서 상태 확인 (`check_certificate.sh`)
```bash
# 인증서 만료일 확인 및 경고
./scripts/ssl/check_certificate.sh

# 특정 도메인 확인
./scripts/ssl/check_certificate.sh example.com
```

**확인 항목:**
- 인증서 만료일
- 남은 일수
- 만료 30일 전 경고
- 만료 7일 전 긴급 알림
- 이미 만료된 경우 즉시 알림

#### 2. 인증서 수동 갱신 (`renew_certificate.sh`)
```bash
# 인증서 갱신 (필요할 때만 실행)
./scripts/ssl/renew_certificate.sh
```

**주의:** 이 스크립트는 실제로 인증서를 갱신합니다. 자동 갱신이 작동 중이면 일반적으로 필요 없습니다.

### 자동 모니터링 설정 (선택사항)
```bash
# crontab에 추가하여 매일 확인 (읽기 전용, 안전)
0 9 * * * /path/to/scripts/ssl/check_certificate.sh >> /var/log/ssl-check.log 2>&1

# 또는 통합 스크립트 사용
0 9 * * * /path/to/scripts/ssl/ssl_manager.sh check >> /var/log/ssl-check.log 2>&1
```

## 참고사항
- Let's Encrypt 인증서는 90일마다 갱신 필요
- 최초 발급은 수동으로 진행 필요
- 갱신은 만료 30일 전 자동으로 진행
- certbot 서비스가 항상 실행 중이어야 자동 갱신 작동
- 인증서 모니터링 스크립트로 만료일 확인 가능

