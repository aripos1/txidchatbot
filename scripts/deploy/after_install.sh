#!/bin/bash

# Let's Encrypt 인증서 자동 갱신 설정

echo "Setting up SSL certificate auto-renewal..."

# Docker Compose 환경 확인
if [ -f "docker-compose.yml" ]; then
    echo "Docker Compose environment detected"
    
    # certbot 서비스가 시작되었는지 확인
    if docker-compose ps certbot | grep -q "Up"; then
        echo "Certbot service is running and will auto-renew certificates"
    else
        echo "Starting certbot service for auto-renewal..."
        docker-compose up -d certbot
    fi
    
elif [ -f /etc/letsencrypt/live/txid.shop/fullchain.pem ]; then
    # 인증서가 존재하는 경우
    echo "SSL certificate found"
    
    # 일반 환경에서 자동 갱신 설정
    if command -v systemctl &> /dev/null; then
        # systemd가 있는 경우 (일반 리눅스)
        echo "Setting up systemd service..."
        
        # certbot renew를 자동으로 실행하는 cronjob 추가
        if ! grep -q "certbot renew" /etc/crontab; then
            sudo bash -c 'echo "0 2 * * 0 certbot renew --quiet --deploy-hook \"systemctl reload nginx\"" >> /etc/crontab'
            echo "Cron job added for certificate renewal"
        else
            echo "Cron job already exists"
        fi
    elif command -v launchctl &> /dev/null; then
        # macOS의 경우
        echo "macOS detected, skipping systemctl configuration"
    else
        # 기타 시스템
        echo "Unsupported system, please set up SSL certificate renewal manually"
    fi
    
else
    # 인증서가 없는 경우
    echo "SSL certificate not found."
    echo "For Docker: Install certificate manually: docker-compose exec certbot certbot certonly --webroot -w /var/www/html -d txid.shop"
    echo "For standalone: sudo certbot certonly --standalone -d txid.shop"
fi

echo "AfterInstall completed successfully"

