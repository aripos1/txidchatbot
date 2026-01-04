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

## 참고사항
- Let's Encrypt 인증서는 90일마다 갱신 필요
- 최초 발급은 수동으로 진행 필요
- 갱신은 만료 30일 전 자동으로 진행
- certbot 서비스가 항상 실행 중이어야 자동 갱신 작동

