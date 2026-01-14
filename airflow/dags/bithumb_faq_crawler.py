"""
빗썸 FAQ 크롤링 Airflow DAG
매일 자동으로 빗썸 고객지원 센터 FAQ를 크롤링하여 MongoDB Atlas에 저장합니다.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
# Airflow 컨테이너에서는 /opt/airflow/project로 마운트됨
project_root = Path('/opt/airflow/project')
if not project_root.exists():
    # 로컬 개발 환경에서는 상대 경로 사용
    project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 환경 변수 로드
from dotenv import load_dotenv
env_file = project_root / '.env'
if env_file.exists():
    load_dotenv(env_file)

default_args = {
    'owner': 'bithumb-crawler',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 1, 1),
}

dag = DAG(
    'bithumb_faq_crawler',
    default_args=default_args,
    description='빗썸 FAQ 크롤링 및 MongoDB Atlas 저장',
    schedule_interval='0 2 * * *',  # 매일 오전 2시 실행
    catchup=False,
    tags=['bithumb', 'crawler', 'faq', 'mongodb'],
)


def run_crawl_bithumb_faq():
    """빗썸 FAQ 크롤링 스크립트 실행"""
    import asyncio
    import logging
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 크롤링 스크립트 실행
    from scripts.data.crawl_bithumb import main
    
    try:
        asyncio.run(main())
        logging.info("빗썸 FAQ 크롤링 완료")
    except Exception as e:
        logging.error(f"빗썸 FAQ 크롤링 실패: {e}")
        raise


# 크롤링 작업
crawl_task = PythonOperator(
    task_id='crawl_bithumb_faq',
    python_callable=run_crawl_bithumb_faq,
    dag=dag,
)

# 작업 실행 순서 정의
crawl_task
