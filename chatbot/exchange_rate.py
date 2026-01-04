"""
환율 정보 조회 모듈
환율 API를 우선 사용하고, 실패 시 웹 검색으로 폴백
"""
import os
import logging
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from .configuration import config

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """환율 정보 조회 서비스"""
    
    # 무료 환율 API 엔드포인트 (환경 변수로 설정 가능)
    EXCHANGERATE_API_KEY: Optional[str] = os.getenv("EXCHANGERATE_API_KEY")
    EXCHANGERATE_API_URL: str = config.EXCHANGE_RATE_API_URL
    
    # 대체 API (환경 변수로 설정 가능)
    FIXER_API_KEY: Optional[str] = os.getenv("FIXER_API_KEY")
    FIXER_API_URL: str = "https://api.fixer.io/latest"
    
    # 캐시 (하루 동안 유효)
    _cache: dict = {}
    _cache_date: Optional[str] = None
    
    @classmethod
    async def get_usd_krw_rate(cls, target_date: Optional[datetime] = None) -> Optional[float]:
        """
        USD/KRW 환율 조회
        
        Args:
            target_date: 조회할 날짜 (None이면 오늘, 전일 환율은 target_date - 1일)
        
        Returns:
            USD/KRW 환율 (예: 1472.40) 또는 None (조회 실패 시)
        """
        # 전일 환율 조회
        if target_date:
            # 전일 날짜 계산
            kst = timezone(timedelta(hours=9))
            yesterday = (target_date - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            cache_key = f"USD_KRW_{yesterday.strftime('%Y-%m-%d')}"
        else:
            # 오늘 환율
            kst = timezone(timedelta(hours=9))
            today = datetime.now(kst).replace(hour=0, minute=0, second=0, microsecond=0)
            cache_key = f"USD_KRW_{today.strftime('%Y-%m-%d')}"
        
        # 캐시 확인
        if cls._cache_date == cache_key and cache_key in cls._cache:
            logger.info(f"환율 캐시 사용: {cls._cache[cache_key]}")
            return cls._cache[cache_key]
        
        # API 우선 시도
        rate = await cls._fetch_from_api(target_date)
        
        if rate:
            # 캐시 저장
            cls._cache[cache_key] = rate
            cls._cache_date = cache_key
            logger.info(f"✅ 환율 API 조회 성공: {rate} KRW/USD")
            return rate
        
        logger.warning("⚠️ 환율 API 조회 실패 - 웹 검색으로 폴백 필요")
        return None
    
    @classmethod
    async def _fetch_from_api(cls, target_date: Optional[datetime] = None) -> Optional[float]:
        """환율 API에서 환율 조회"""
        try:
            # exchangerate-api.com 시도 (무료, API 키 불필요)
            async with httpx.AsyncClient(timeout=5.0) as client:
                # 오늘 환율 조회
                response = await client.get(cls.EXCHANGERATE_API_URL)
                if response.status_code == 200:
                    data = response.json()
                    if "rates" in data and "KRW" in data["rates"]:
                        rate = float(data["rates"]["KRW"])
                        logger.info(f"exchangerate-api.com에서 환율 조회 성공: {rate}")
                        return rate
                
                # 전일 환율 조회 (target_date가 있는 경우)
                if target_date:
                    yesterday = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")
                    historical_url = f"https://api.exchangerate-api.com/v4/historical/USD/{yesterday}"
                    response = await client.get(historical_url)
                    if response.status_code == 200:
                        data = response.json()
                        if "rates" in data and "KRW" in data["rates"]:
                            rate = float(data["rates"]["KRW"])
                            logger.info(f"exchangerate-api.com에서 전일 환율 조회 성공: {rate} ({yesterday})")
                            return rate
        except Exception as e:
            logger.warning(f"exchangerate-api.com 조회 실패: {e}")
        
        # Fixer.io 시도 (API 키 필요)
        if cls.FIXER_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    url = f"{cls.FIXER_API_URL}?access_key={cls.FIXER_API_KEY}&base=USD&symbols=KRW"
                    if target_date:
                        yesterday = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")
                        url = f"{cls.FIXER_API_URL}/{yesterday}?access_key={cls.FIXER_API_KEY}&base=USD&symbols=KRW"
                    
                    response = await client.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        if "rates" in data and "KRW" in data["rates"]:
                            rate = float(data["rates"]["KRW"])
                            logger.info(f"fixer.io에서 환율 조회 성공: {rate}")
                            return rate
            except Exception as e:
                logger.warning(f"fixer.io 조회 실패: {e}")
        
        return None
    
    @classmethod
    def clear_cache(cls):
        """캐시 초기화"""
        cls._cache.clear()
        cls._cache_date = None


# 전역 인스턴스
exchange_rate_service = ExchangeRateService()

