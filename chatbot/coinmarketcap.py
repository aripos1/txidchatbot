"""
코인마켓캡(CoinMarketCap) API 서비스
암호화폐 시세 정보 조회
"""
import os
import logging
import httpx
from typing import Optional, Dict, List
from datetime import datetime, timezone, timedelta
from .configuration import config

logger = logging.getLogger(__name__)


class CoinMarketCapService:
    """코인마켓캡 API 서비스"""
    
    # API 키 (환경 변수에서 가져오기)
    API_KEY: Optional[str] = os.getenv("COINMARKETCAP_API_KEY")
    BASE_URL: str = config.COINMARKETCAP_API_URL
    
    # 캐시 (5분 동안 유효)
    _cache: Dict[str, tuple] = {}  # {symbol: (data, timestamp)}
    CACHE_DURATION: int = 300  # 5분 (초)
    
    # 코인 심볼 매핑 (한국어 → 영어 심볼)
    SYMBOL_MAPPING: Dict[str, str] = {
        '비트코인': 'BTC',
        '이더리움': 'ETH',
        '리플': 'XRP',
        '비트코인캐시': 'BCH',
        '라이트코인': 'LTC',
        '이더리움클래식': 'ETC',
        '도지코인': 'DOGE',
        '트론': 'TRX',
        '에이다': 'ADA',
        '솔라나': 'SOL',
        '폴카닷': 'DOT',
        '체인링크': 'LINK',
        '유니스왑': 'UNI',
        '아발란체': 'AVAX',
        '폴리곤': 'MATIC',
        '스텔라루멘': 'XLM',
        '비체인': 'VET',
        '파일코인': 'FIL',
        '테조스': 'XTZ',
        '이오스': 'EOS',
    }
    
    @classmethod
    def _get_symbol(cls, coin_name: str) -> Optional[str]:
        """한국어 코인명을 영어 심볼로 변환"""
        coin_lower = coin_name.lower().strip()
        
        # 직접 매핑 확인
        if coin_lower in cls.SYMBOL_MAPPING:
            return cls.SYMBOL_MAPPING[coin_lower]
        
        # 부분 매칭 (예: "비트코인 가격" → "BTC")
        for korean, symbol in cls.SYMBOL_MAPPING.items():
            if korean in coin_lower:
                return symbol
        
        # 이미 영어 심볼인 경우 (대문자 변환)
        if coin_lower.isalpha() and len(coin_lower) <= 10:
            return coin_lower.upper()
        
        return None
    
    @classmethod
    async def get_price(cls, coin_name: str, convert: str = "KRW", target_date: Optional[datetime] = None) -> Optional[Dict]:
        """
        코인 가격 조회 (현재 또는 과거 날짜)
        
        Args:
            coin_name: 코인명 (한국어 또는 영어 심볼)
            convert: 변환 통화 (기본값: KRW)
            target_date: 조회할 날짜 (None이면 현재 시세, 지정하면 과거 시세)
        
        Returns:
            {
                "symbol": "BTC",
                "name": "Bitcoin",
                "price_usd": 95000.0,
                "price_krw": 140000000.0,
                "price_change_24h": -2.5,
                "market_cap": 1800000000000,
                "last_updated": "2025-12-18T00:00:00Z"
            } 또는 None
        """
        if not cls.API_KEY:
            logger.warning("⚠️ COINMARKETCAP_API_KEY가 설정되지 않았습니다.")
            return None
        
        # 심볼 추출
        symbol = cls._get_symbol(coin_name)
        if not symbol:
            logger.warning(f"⚠️ 코인 심볼을 찾을 수 없습니다: {coin_name}")
            return None
        
        # 캐시 확인 (과거 날짜는 캐시 사용 안 함)
        cache_key = f"{symbol}_{convert}"
        if not target_date and cache_key in cls._cache:
            data, timestamp = cls._cache[cache_key]
            if (datetime.now().timestamp() - timestamp) < cls.CACHE_DURATION:
                logger.info(f"✅ 코인마켓캡 캐시 사용: {symbol}")
                return data
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 과거 날짜인 경우 historical 엔드포인트 사용
                if target_date:
                    # 코인마켓캡 Historical API는 ID가 필요하므로 먼저 ID를 가져와야 함
                    # 1단계: latest API로 ID 가져오기
                    latest_url = f"{cls.BASE_URL}/cryptocurrency/quotes/latest"
                    latest_params = {
                        "symbol": symbol,
                        "convert": convert
                    }
                    
                    latest_response = await client.get(latest_url, headers=headers, params=latest_params)
                    if latest_response.status_code != 200:
                        logger.warning(f"⚠️ 코인마켓캡 ID 조회 실패: {latest_response.status_code}")
                        return None
                    
                    latest_data = latest_response.json()
                    if "data" not in latest_data or symbol not in latest_data["data"]:
                        logger.warning(f"⚠️ 코인마켓캡 ID 조회 실패: 심볼 {symbol}을 찾을 수 없음")
                        return None
                    
                    # ID 추출
                    coin_info = latest_data["data"][symbol]
                    if isinstance(coin_info, list):
                        coin_id = coin_info[0].get("id")
                    elif isinstance(coin_info, dict):
                        coin_id = coin_info.get("id")
                    else:
                        logger.warning(f"⚠️ 코인마켓캡 ID 추출 실패")
                        return None
                    
                    if not coin_id:
                        logger.warning(f"⚠️ 코인마켓캡 ID를 찾을 수 없음")
                        return None
                    
                    # 2단계: Historical API로 과거 시세 조회
                    url = f"{cls.BASE_URL}/cryptocurrency/quotes/historical"
                    date_str = target_date.strftime("%Y-%m-%d")
                    # time_start와 time_end를 ISO 8601 형식으로 변환 (타임스탬프)
                    from datetime import timezone as tz
                    target_datetime_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz.utc)
                    target_datetime_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=tz.utc)
                    
                    params = {
                        "id": str(coin_id),  # ID 사용
                        "convert": convert,
                        "time_start": target_datetime_start.isoformat(),
                        "time_end": target_datetime_end.isoformat(),
                        "count": 1,
                        "interval": "daily"  # 일일 데이터
                    }
                    logger.info(f"코인마켓캡 과거 시세 조회: {symbol} (ID: {coin_id}, 날짜: {date_str})")
                else:
                    url = f"{cls.BASE_URL}/cryptocurrency/quotes/latest"
                    params = {
                        "symbol": symbol,
                        "convert": convert
                    }
                
                headers = {
                    "X-CMC_PRO_API_KEY": cls.API_KEY,
                    "Accept": "application/json"
                }
                
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # 응답 구조 확인을 위한 디버깅
                    logger.debug(f"코인마켓캡 API 응답 구조: {list(data.keys())}")
                    
                    # 에러 응답 확인
                    if "status" in data and data.get("status", {}).get("error_code", 0) != 0:
                        error_message = data.get("status", {}).get("error_message", "Unknown error")
                        logger.error(f"❌ 코인마켓캡 API 오류: {error_message}")
                        return None
                    
                    if "data" not in data:
                        logger.warning(f"⚠️ 코인마켓캡 API 응답에 'data' 키가 없습니다. 응답: {data}")
                        if target_date:
                            logger.info("과거 날짜 조회 실패 - 웹 검색으로 폴백 필요")
                        return None
                    
                    # Historical API와 Latest API의 응답 구조가 다름
                    coin_data = None
                    if target_date:
                        # Historical API: data 안에 id가 키로 사용됨
                        if str(coin_id) not in data["data"]:
                            logger.warning(f"⚠️ 코인마켓캡 Historical API 응답에 ID '{coin_id}'가 없습니다. 사용 가능한 ID: {list(data['data'].keys())}")
                            logger.info("과거 날짜 조회 실패 - 웹 검색으로 폴백 필요")
                            return None
                        
                        historical_data = data["data"][str(coin_id)]
                        # Historical API는 quotes 배열을 반환
                        if "quotes" in historical_data and len(historical_data["quotes"]) > 0:
                            # 가장 가까운 날짜의 데이터 사용
                            quote_item = historical_data["quotes"][0]
                            # Historical API 응답 구조에 맞게 변환
                            coin_data = {
                                "id": coin_id,
                                "symbol": symbol,
                                "name": historical_data.get("name", coin_name),
                                "quote": quote_item.get("quote", {})
                            }
                            logger.debug(f"Historical API 데이터 추출 성공: {symbol}")
                        else:
                            logger.warning(f"⚠️ 코인마켓캡 Historical API 응답에 quotes가 없습니다.")
                            logger.info("과거 날짜 조회 실패 - 웹 검색으로 폴백 필요")
                            return None
                    else:
                        # Latest API: symbol이 키로 사용됨
                        if symbol not in data["data"]:
                            logger.warning(f"⚠️ 코인마켓캡 API 응답에 '{symbol}' 심볼이 없습니다. 사용 가능한 심볼: {list(data['data'].keys())}")
                            return None
                        
                        coin_data_list = data["data"][symbol]
                        
                        # 응답 구조 확인: 배열인지 딕셔너리인지 확인
                        try:
                            if isinstance(coin_data_list, dict):
                                # 딕셔너리인 경우 (단일 코인)
                                if not coin_data_list:
                                    logger.warning(f"⚠️ 코인마켓캡 API 응답에 '{symbol}' 데이터가 비어있습니다.")
                                    return None
                                coin_data = coin_data_list
                                logger.debug(f"코인 데이터 타입: dict, 키: {list(coin_data.keys())[:5]}")
                            elif isinstance(coin_data_list, list):
                                # 배열인 경우 (여러 코인 중 첫 번째)
                                if len(coin_data_list) == 0:
                                    logger.warning(f"⚠️ 코인마켓캡 API 응답에 '{symbol}' 데이터가 비어있습니다.")
                                    return None
                                coin_data = coin_data_list[0]
                                logger.debug(f"코인 데이터 타입: list, 첫 번째 요소 타입: {type(coin_data)}")
                            else:
                                logger.warning(f"⚠️ 코인마켓캡 API 응답 구조가 예상과 다릅니다. 타입: {type(coin_data_list)}, 값: {str(coin_data_list)[:200]}")
                                return None
                        except Exception as e:
                            logger.error(f"❌ 코인 데이터 추출 중 오류: {e}, coin_data_list 타입: {type(coin_data_list)}")
                            return None
                    
                    if coin_data is None:
                        logger.error(f"❌ 코인 데이터를 추출할 수 없습니다.")
                        return None
                    quote = coin_data.get("quote", {})
                    
                    if convert not in quote:
                        logger.warning(f"⚠️ 코인마켓캡 API 응답에 '{convert}' 통화 정보가 없습니다. 사용 가능한 통화: {list(quote.keys())}")
                        return None
                    
                    quote_data = quote[convert]
                    
                    # USD 가격도 함께 가져오기
                    price_usd = 0
                    if "USD" in quote:
                        price_usd = quote["USD"].get("price", 0)
                    elif convert == "USD":
                        price_usd = quote_data.get("price", 0)
                    
                    price_krw = quote_data.get("price", 0) if convert == "KRW" else None
                    
                    if price_krw == 0 and convert == "KRW":
                        logger.warning(f"⚠️ 코인마켓캡 API 응답에서 KRW 가격이 0입니다. quote_data: {quote_data}")
                        # USD 가격이 있으면 사용
                        if price_usd > 0:
                            logger.info(f"USD 가격 사용: {price_usd}")
                            price_krw = None  # USD만 사용
                    
                    result = {
                        "symbol": coin_data.get("symbol", symbol),
                        "name": coin_data.get("name", coin_name),
                        "price_usd": price_usd,
                        "price_krw": price_krw,
                        "price_change_24h": quote_data.get("percent_change_24h", 0),
                        "market_cap": quote_data.get("market_cap", 0),
                        "volume_24h": quote_data.get("volume_24h", 0),
                        "last_updated": coin_data.get("last_updated", "")
                    }
                    
                    # 가격이 0이면 실패로 간주
                    if result["price_usd"] == 0 and result["price_krw"] == 0:
                        logger.error(f"❌ 코인마켓캡 API 조회 실패: 가격 정보가 없습니다. 응답: {data}")
                        return None
                    
                    # 캐시 저장
                    cls._cache[cache_key] = (result, datetime.now().timestamp())
                    
                    price_display = result['price_krw'] if result['price_krw'] else result['price_usd']
                    currency_display = convert if result['price_krw'] else "USD"
                    logger.info(f"✅ 코인마켓캡 API 조회 성공: {symbol} = {price_display:,.2f} {currency_display}")
                    return result
                else:
                    error_text = response.text[:500] if hasattr(response, 'text') else str(response.content[:500])
                    logger.warning(f"⚠️ 코인마켓캡 API 오류: {response.status_code} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ 코인마켓캡 API 조회 실패: {e}", exc_info=True)
            return None
    
    @classmethod
    async def search_coins(cls, query: str) -> List[Dict]:
        """
        코인 검색 (이름으로 검색)
        
        Args:
            query: 검색어
        
        Returns:
            코인 정보 리스트
        """
        if not cls.API_KEY:
            return []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{cls.BASE_URL}/cryptocurrency/search"
                headers = {
                    "X-CMC_PRO_API_KEY": cls.API_KEY,
                    "Accept": "application/json"
                }
                params = {
                    "query": query,
                    "limit": 10
                }
                
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data:
                        return data["data"]
                return []
        except Exception as e:
            logger.error(f"❌ 코인마켓캡 검색 실패: {e}")
            return []
    
    @classmethod
    def clear_cache(cls):
        """캐시 초기화"""
        cls._cache.clear()


# 전역 인스턴스
coinmarketcap_service = CoinMarketCapService()

