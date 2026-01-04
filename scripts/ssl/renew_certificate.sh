#!/bin/bash

# Let's Encrypt 인증서 수동 갱신 스크립트

echo "Starting SSL certificate renewal..."

# Docker Compose 환경 감지
if [ -f "docker-compose.yml" ]; then
    echo "Docker Compose environment detected"
    
    # certbot 컨테이너를 통해 갱신
    docker-compose exec certbot certbot renew --webroot --webroot-path=/var/www/html --force-renewal
    
    if [ $? -eq 0 ]; then
        echo "Certificate renewal successful"
        docker-compose restart nginx
        echo "Nginx restarted with new certificate"
    else
        echo "Certificate renewal failed"
        exit 1
    fi
else
    # 일반 환경
    sudo certbot renew --force-renewal
    
    if [ $? -eq 0 ]; then
        echo "Certificate renewal successful"
        
        # nginx 재시작 (인증서 적용)
        if command -v systemctl &> /dev/null; then
            sudo systemctl reload nginx
        else
            echo "Please manually restart nginx to apply the new certificate"
        fi
        
        echo "SSL certificate renewal completed"
    else
        echo "Certificate renewal failed"
        exit 1
    fi
fi

