FROM apache/airflow:2.8.0

USER root

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 커스텀 엔트리포인트 복사 (빌드 컨텍스트가 프로젝트 루트이므로)
COPY --chown=airflow:root airflow/entrypoint.sh /custom-entrypoint.sh
RUN chmod +x /custom-entrypoint.sh

USER airflow

# Airflow 추가 패키지 설치
RUN pip install --no-cache-dir \
    apache-airflow-providers-postgres==5.10.0 \
    psycopg2-binary==2.9.9

WORKDIR /opt/airflow

# 엔트리포인트는 docker-compose에서 오버라이드
