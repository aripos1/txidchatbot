#!/bin/bash

# SSL 인증서 통합 관리 스크립트
# 사용법: ./scripts/ssl/ssl_manager.sh [check|renew] [도메인]

set -e

ACTION=${1:-check}
DOMAIN=${2:-txid.shop}

case "$ACTION" in
    check)
        echo "인증서 상태 확인 중..."
        exec "$(dirname "$0")/check_certificate.sh" "$DOMAIN"
        ;;
    renew)
        echo "인증서 갱신 중..."
        exec "$(dirname "$0")/renew_certificate.sh"
        ;;
    *)
        echo "사용법: $0 [check|renew] [도메인]"
        echo ""
        echo "명령어:"
        echo "  check  - 인증서 상태 확인 (기본값)"
        echo "  renew  - 인증서 수동 갱신"
        echo ""
        echo "예시:"
        echo "  $0 check           # 기본 도메인(txid.shop) 확인"
        echo "  $0 check example.com  # 특정 도메인 확인"
        echo "  $0 renew           # 인증서 갱신"
        exit 1
        ;;
esac
