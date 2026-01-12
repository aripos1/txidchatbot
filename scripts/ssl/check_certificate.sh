#!/bin/bash

# SSL 인증서 만료일 확인 및 모니터링 스크립트
# 사용법: ./scripts/ssl/check_certificate.sh [도메인]

set -e

DOMAIN=${1:-txid.shop}
WARNING_DAYS=30  # 만료 30일 전 경고
ALERT_DAYS=7     # 만료 7일 전 알림

echo "=========================================="
echo "SSL 인증서 상태 확인: $DOMAIN"
echo "=========================================="

# Docker Compose 환경 감지
if [ -f "docker-compose.yml" ]; then
    echo "Docker Compose 환경 감지"
    
    # certbot 컨테이너를 통해 인증서 확인
    CERT_INFO=$(docker-compose exec -T certbot certbot certificates 2>/dev/null | grep -A 10 "$DOMAIN" || echo "")
    
    if [ -z "$CERT_INFO" ]; then
        echo "❌ 인증서를 찾을 수 없습니다."
        echo "   인증서를 발급하려면:"
        echo "   docker-compose exec certbot certbot certonly --webroot -w /var/www/html -d $DOMAIN"
        exit 1
    fi
    
    # 만료일 추출 (certbot certificates 출력에서)
    EXPIRY_DATE=$(docker-compose exec -T certbot certbot certificates 2>/dev/null | grep -A 10 "$DOMAIN" | grep "Expiry Date" | awk '{print $3, $4, $5, $6, $7}' || echo "")
    
    if [ -z "$EXPIRY_DATE" ]; then
        echo "⚠️ 만료일을 확인할 수 없습니다."
        echo "인증서 정보:"
        echo "$CERT_INFO"
        exit 0
    fi
    
    # 만료일을 Unix timestamp로 변환
    EXPIRY_TIMESTAMP=$(date -d "$EXPIRY_DATE" +%s 2>/dev/null || echo "")
    
else
    # 일반 환경
    CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
    
    if [ ! -f "$CERT_PATH" ]; then
        echo "❌ 인증서를 찾을 수 없습니다: $CERT_PATH"
        echo "   인증서를 발급하려면:"
        echo "   sudo certbot certonly --standalone -d $DOMAIN"
        exit 1
    fi
    
    # OpenSSL을 사용하여 만료일 확인
    EXPIRY_DATE=$(openssl x509 -enddate -noout -in "$CERT_PATH" | cut -d= -f2)
    EXPIRY_TIMESTAMP=$(date -d "$EXPIRY_DATE" +%s 2>/dev/null || echo "")
fi

if [ -z "$EXPIRY_TIMESTAMP" ]; then
    echo "⚠️ 만료일을 파싱할 수 없습니다."
    exit 1
fi

# 현재 시간
CURRENT_TIMESTAMP=$(date +%s)

# 남은 일수 계산
DAYS_UNTIL_EXPIRY=$(( ($EXPIRY_TIMESTAMP - $CURRENT_TIMESTAMP) / 86400 ))

echo ""
echo "인증서 정보:"
echo "  도메인: $DOMAIN"
echo "  만료일: $EXPIRY_DATE"
echo "  남은 일수: $DAYS_UNTIL_EXPIRY일"

# 상태 확인 및 알림
if [ $DAYS_UNTIL_EXPIRY -lt 0 ]; then
    echo ""
    echo "🚨 경고: 인증서가 이미 만료되었습니다!"
    echo "   즉시 인증서를 갱신하세요:"
    if [ -f "docker-compose.yml" ]; then
        echo "   ./scripts/ssl/renew_certificate.sh"
    else
        echo "   sudo certbot renew --force-renewal"
    fi
    exit 2
elif [ $DAYS_UNTIL_EXPIRY -lt $ALERT_DAYS ]; then
    echo ""
    echo "🚨 긴급: 인증서가 $DAYS_UNTIL_EXPIRY일 후 만료됩니다!"
    echo "   즉시 인증서를 갱신하세요:"
    if [ -f "docker-compose.yml" ]; then
        echo "   ./scripts/ssl/renew_certificate.sh"
    else
        echo "   sudo certbot renew --force-renewal"
    fi
    exit 1
elif [ $DAYS_UNTIL_EXPIRY -lt $WARNING_DAYS ]; then
    echo ""
    echo "⚠️ 경고: 인증서가 $DAYS_UNTIL_EXPIRY일 후 만료됩니다."
    echo "   곧 인증서를 갱신하는 것을 권장합니다."
    exit 0
else
    echo ""
    echo "✅ 인증서 상태 정상 (만료까지 $DAYS_UNTIL_EXPIRY일 남음)"
    exit 0
fi
