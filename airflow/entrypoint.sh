#!/bin/bash
# Airflow 커스텀 엔트리포인트
# 프로젝트 requirements.txt를 설치한 후 Airflow 실행

set -e

# 프로젝트 requirements.txt가 있으면 설치
if [ -f /opt/airflow/project/requirements.txt ]; then
    echo "Installing project requirements..."
    pip install --no-cache-dir -r /opt/airflow/project/requirements.txt || echo "Warning: Failed to install some requirements"
fi

# 원본 Airflow 엔트리포인트 실행
exec /entrypoint "$@"
