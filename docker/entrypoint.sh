#!/bin/bash
set -e

echo "Starting application..."

# 환경 변수 확인
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Warning: OPENAI_API_KEY is not set"
fi

if [ -z "$MONGODB_URI" ]; then
    echo "Warning: MONGODB_URI is not set"
fi

# Python 애플리케이션 실행
exec "$@"

