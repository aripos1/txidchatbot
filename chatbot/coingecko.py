"""
코인게코(CoinGecko) API 서비스
암호화폐 시세 정보 조회 (과거 시세 포함, 무료)
"""
import os
import logging
import httpx
from typing import Optional, Dict
from datetime import datetime, timezone, timedelta
from .configuration import config

logger = logging.getLogger(__name__)


class CoinGeckoService:
    """코인게코 API 서비스 (무료, 과거 시세 지원)"""
    
    BASE_URL: str = config.COINGECKO_API_URL
    # API 키는 선택사항 (무료 플랜도 사용 가능)
    API_KEY: Optional[str] = os.getenv("COINGECKO_API_KEY")
    
    # 캐시 (5분 동안 유효)
    _cache: Dict[str, tuple] = {}
    CACHE_DURATION: int = 300  # 5분 (초)
    
    # 코인 ID 매핑 (한국어 → CoinGecko ID)
    COIN_ID_MAPPING: Dict[str, str] = {
        '비트코인': 'bitcoin',
        '이더리움': 'ethereum',
        '리플': 'ripple',
        '비트코인캐시': 'bitcoin-cash',
        '라이트코인': 'litecoin',
        '이더리움클래식': 'ethereum-classic',
        '도지코인': 'dogecoin',
        '트론': 'tron',
        '에이다': 'cardano',
        '솔라나': 'solana',
        '폴카닷': 'polkadot',
        '체인링크': 'chainlink',
        '유니스왑': 'uniswap',
        '아발란체': 'avalanche-2',
        '폴리곤': 'matic-network',
        '스텔라루멘': 'stellar',
        '비체인': 'vechain',
        '파일코인': 'filecoin',
        '테조스': 'tezos',
        '이오스': 'eos',
    }
    
    # 심볼 → ID 매핑
    SYMBOL_TO_ID: Dict[str, str] = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'XRP': 'ripple',
        'BCH': 'bitcoin-cash',
        'LTC': 'litecoin',
        'ETC': 'ethereum-classic',
        'DOGE': 'dogecoin',
        'TRX': 'tron',
        'ADA': 'cardano',
        'SOL': 'solana',
        'DOT': 'polkadot',
        'LINK': 'chainlink',
        'UNI': 'uniswap',
        'AVAX': 'avalanche-2',
        'MATIC': 'matic-network',
        'XLM': 'stellar',
        'VET': 'vechain',
        'FIL': 'filecoin',
        'XTZ': 'tezos',
        'EOS': 'eos',
    }
    
    @classmethod
    def _get_coin_id(cls, coin_name: str) -> Optional[str]:
        """한국어 코인명 또는 심볼을 CoinGecko ID로 변환"""
        coin_lower = coin_name.lower().strip()
        
        # 직접 매핑 확인
        if coin_lower in cls.COIN_ID_MAPPING:
            return cls.COIN_ID_MAPPING[coin_lower]
        
        # 심볼 매핑 확인
        if coin_lower.upper() in cls.SYMBOL_TO_ID:
            return cls.SYMBOL_TO_ID[coin_lower.upper()]
        
        # 부분 매칭 (예: "비트코인 가격" → "bitcoin")
        for korean, coin_id in cls.COIN_ID_MAPPING.items():
            if korean in coin_lower:
                return coin_id
        
        return None
    
    @classmethod
    async def get_price(cls, coin_name: str, convert: str = "krw", target_date: Optional[datetime] = None) -> Optional[Dict]:
        """
        코인 가격 조회 (현재 또는 과거 날짜)
        
        Args:
            coin_name: 코인명 (한국어 또는 영어 심볼)
            convert: 변환 통화 (기본값: krw, 소문자)
            target_date: 조회할 날짜 (None이면 현재 시세, 지정하면 과거 시세)
                        주의: 무료 플랜은 최근 365일 이내 데이터만 조회 가능
        
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
        # CoinGecko는 소문자 통화 코드 사용
        convert_lower = convert.lower()
        
        # 코인 ID 추출
        coin_id = cls._get_coin_id(coin_name)
        if not coin_id:
            logger.warning(f"⚠️ 코인게코 ID를 찾을 수 없습니다: {coin_name}")
            return None
        
        # 과거 날짜 조회 시 365일 제한 확인 (무료 플랜)
        if target_date:
            now = datetime.now(timezone.utc)
            # 날짜만 비교 (시간 제외)
            target_date_utc = target_date.replace(tzinfo=timezone.utc) if target_date.tzinfo is None else target_date
            days_diff = (now.date() - target_date_utc.date()).days
            
            # 무료 플랜은 최근 365일 이내만 조회 가능
            if days_diff > 365:
                logger.warning(
                    f"⚠️ 코인게코 무료 플랜 제한: 요청한 날짜({target_date_utc.date()})가 "
                    f"현재로부터 {days_diff}일 전입니다. 무료 플랜은 최근 365일 이내 데이터만 조회 가능합니다."
                )
                return None
        
        # 캐시 확인 (과거 날짜는 캐시 사용 안 함)
        cache_key = f"{coin_id}_{convert_lower}_{target_date.strftime('%Y-%m-%d') if target_date else 'latest'}"
        if cache_key in cls._cache:
            data, timestamp = cls._cache[cache_key]
            if (datetime.now().timestamp() - timestamp) < cls.CACHE_DURATION:
                logger.info(f"✅ 코인게코 캐시 사용: {coin_id}")
                return data
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "Accept": "application/json"
                }
                
                # API 키가 있으면 헤더에 추가 (선택사항)
                if cls.API_KEY:
                    headers["x-cg-demo-api-key"] = cls.API_KEY
                
                if target_date:
                    # 과거 날짜 조회: /coins/{id}/history
                    url = f"{cls.BASE_URL}/coins/{coin_id}/history"
                    # CoinGecko는 날짜를 DD-MM-YYYY 형식으로 받음
                    date_str = target_date.strftime("%d-%m-%Y")
                    params = {
                        "date": date_str,
                        "localization": "false"
                    }
                    logger.info(f"코인게코 과거 시세 조회: {coin_id} ({date_str})")
                else:
                    # 현재 시세 조회: /simple/price
                    url = f"{cls.BASE_URL}/simple/price"
                    params = {
                        "ids": coin_id,
                        "vs_currencies": f"{convert_lower},usd",
                        "include_24hr_change": "true",
                        "include_market_cap": "true",
                        "include_24hr_vol": "true"
                    }
                
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if target_date:
                        # Historical API 응답 처리
                        if "market_data" not in data:
                            logger.warning(f"⚠️ 코인게코 Historical API 응답에 market_data가 없습니다.")
                            return None
                        
                        market_data = data["market_data"]
                        current_price = market_data.get("current_price", {})
                        
                        price_krw = current_price.get(convert_lower, 0)
                        price_usd = current_price.get("usd", 0)
                        
                        result = {
                            "symbol": data.get("symbol", "").upper(),
                            "name": data.get("name", coin_name),
                            "price_usd": price_usd,
                            "price_krw": price_krw if convert_lower == "krw" else None,
                            "price_change_24h": 0,  # Historical API에는 24h change가 없음
                            "market_cap": market_data.get("market_cap", {}).get(convert_lower, 0) if convert_lower == "krw" else market_data.get("market_cap", {}).get("usd", 0),
                            "volume_24h": 0,  # Historical API에는 volume이 없을 수 있음
                            "last_updated": target_date.isoformat()
                        }
                    else:
                        # Latest API 응답 처리
                        if coin_id not in data:
                            logger.warning(f"⚠️ 코인게코 API 응답에 '{coin_id}' 데이터가 없습니다.")
                            return None
                        
                        coin_data = data[coin_id]
                        
                        price_krw = coin_data.get(convert_lower, 0)
                        price_usd = coin_data.get("usd", 0)
                        
                        result = {
                            "symbol": coin_name.upper() if len(coin_name) <= 5 else "",
                            "name": coin_name,
                            "price_usd": price_usd,
                            "price_krw": price_krw if convert_lower == "krw" else None,
                            "price_change_24h": coin_data.get(f"{convert_lower}_24h_change", 0),
                            "market_cap": coin_data.get(f"{convert_lower}_market_cap", 0) if convert_lower == "krw" else coin_data.get("usd_market_cap", 0),
                            "volume_24h": coin_data.get(f"{convert_lower}_24h_vol", 0) if convert_lower == "krw" else coin_data.get("usd_24h_vol", 0),
                            "last_updated": datetime.now(timezone.utc).isoformat()
                        }
                    
                    # 가격이 0이면 실패로 간주
                    if result["price_usd"] == 0 and result["price_krw"] == 0:
                        logger.warning(f"⚠️ 코인게코 API 조회 실패: 가격 정보가 없습니다.")
                        return None
                    
                    # 캐시 저장
                    cls._cache[cache_key] = (result, datetime.now().timestamp())
                    
                    price_display = result['price_krw'] if result['price_krw'] else result['price_usd']
                    currency_display = convert.upper() if result['price_krw'] else "USD"
                    logger.info(f"✅ 코인게코 API 조회 성공: {coin_id} = {price_display:,.2f} {currency_display}")
                    return result
                elif response.status_code == 401:
                    # 401 오류는 주로 날짜 제한 또는 API 키 문제
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    error_message = error_data.get("error", {}).get("status", {}).get("error_message", response.text[:200])
                    
                    if "365 days" in error_message or "time range" in error_message.lower():
                        logger.warning(
                            f"⚠️ 코인게코 무료 플랜 제한: 과거 데이터 조회는 최근 365일 이내만 가능합니다. "
                            f"요청한 날짜: {target_date.strftime('%Y-%m-%d') if target_date else 'N/A'}"
                        )
                    else:
                        logger.warning(f"⚠️ 코인게코 API 인증 오류 (401): {error_message}")
                    if target_date:
                        logger.info("과거 날짜 조회 실패 - 다른 API나 웹 검색으로 폴백 필요")
                    return None
                else:
                    error_text = response.text[:500] if hasattr(response, 'text') else str(response.content[:500])
                    logger.warning(f"⚠️ 코인게코 API 오류: {response.status_code} - {error_text}")
                    if target_date:
                        logger.info("과거 날짜 조회 실패 - 웹 검색으로 폴백 필요")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ 코인게코 API 조회 실패: {e}", exc_info=True)
            if target_date:
                logger.info("과거 날짜 조회 실패 - 웹 검색으로 폴백 필요")
            return None
    
    @classmethod
    def clear_cache(cls):
        """캐시 초기화"""
        cls._cache.clear()


# 전역 인스턴스
coingecko_service = CoinGeckoService()

