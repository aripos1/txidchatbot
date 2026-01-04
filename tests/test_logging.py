"""
로깅 테스트 스크립트
"""
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

# 로깅 설정
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True  # 기존 설정 덮어쓰기
)

logger = logging.getLogger(__name__)

def test_logging():
    """로깅 테스트"""
    logger.info("="*60)
    logger.info("로깅 테스트 시작")
    logger.info(f"로깅 레벨: {log_level_str}")
    logger.info("="*60)
    
    logger.debug("DEBUG 레벨 메시지 (디버그 모드에서만 보임)")
    logger.info("INFO 레벨 메시지 (기본적으로 보임)")
    logger.warning("WARNING 레벨 메시지")
    logger.error("ERROR 레벨 메시지")
    
    logger.info("="*60)
    logger.info("로깅 테스트 완료")
    logger.info("="*60)

if __name__ == "__main__":
    test_logging()

