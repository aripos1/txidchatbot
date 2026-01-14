"""
Researcher 노드 - 웹 검색 수행
"""
import re
import sys
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import httpx
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable

from ...models import ChatState
from ...configuration import config
from ...utils import ensure_logger_setup

# 선택적 의존성 (DuckDuckGo)
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

# 선택적 의존성 (Tavily)
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    TavilyClient = None

logger = logging.getLogger(__name__)


async def _search_single_google_query(client: httpx.AsyncClient, query: str, google_api_key: str, google_cx: str) -> tuple[list, bool]:
    """단일 Google 검색 쿼리 처리 (병렬 처리용)"""
    try:
        url = config.GOOGLE_SEARCH_API_URL
        params = {
            "key": google_api_key,
            "cx": google_cx,
            "q": query,
            "num": min(config.MAX_RESULTS_PER_QUERY, 10),
            "lr": "lang_ko",
        }
        
        response = await client.get(url, params=params)
        
        if response.status_code == 429:
            logger.warning(f"Google API 할당량 초과: {query[:50]}")
            return [], True
        
        if response.status_code != 200:
            return [], False
        
        data = response.json()
        
        if "error" in data:
            error_code = data["error"].get("code", 0)
            if error_code == 429:
                return [], True
            return [], False
        
        results = []
        if "items" in data:
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", ""),
                })
        
        return results, False
        
    except httpx.TimeoutException:
        logger.warning(f"Google 검색 타임아웃: {query[:50]}")
        return [], False
    except Exception as e:
        logger.error(f"Google 검색 오류 ({query[:50]}): {e}")
        return [], False


async def _search_with_google(search_queries: list) -> tuple[list, bool]:
    """Google Custom Search API로 검색 (병렬 처리)"""
    google_api_key = config.GOOGLE_API_KEY
    google_cx = config.GOOGLE_CX
    
    if not google_api_key or not google_cx:
        return [], False
    
    logger.info(f"Google 검색 시작: {len(search_queries)}개 쿼리 (병렬 처리)")
    
    all_results = []
    seen_urls = set()
    rate_limit_hit = False
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 모든 쿼리를 병렬로 처리
        tasks = [
            _search_single_google_query(client, query, google_api_key, google_cx)
            for query in search_queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Google 쿼리 오류 ({search_queries[i][:50]}): {result}")
                continue
            
            query_results, hit_rate_limit = result
            if hit_rate_limit:
                rate_limit_hit = True
            
            for item in query_results:
                url_link = item.get("url", "")
                if url_link and url_link not in seen_urls:
                    seen_urls.add(url_link)
                    all_results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "url": url_link,
                    })
    
    logger.info(f"Google 검색 완료: {len(all_results)}개 결과 (병렬 처리)")
    return all_results, rate_limit_hit


async def _search_single_ddg_query(query: str) -> list:
    """단일 DuckDuckGo 검색 쿼리 처리 (병렬 처리용)"""
    if DDGS is None:
        return []
    
    # site: 쿼리 변환
    processed_query = query
    if 'site:bithumb.com' in query.lower():
        cleaned_query = query.lower().replace('site:bithumb.com', '').strip()
        if '빗썸' not in cleaned_query:
            cleaned_query = f"빗썸 {cleaned_query}"
        processed_query = cleaned_query
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(processed_query, max_results=config.MAX_RESULTS_PER_QUERY))
            return results
    except Exception as e:
        logger.error(f"DuckDuckGo 쿼리 오류 ({query[:50]}): {e}")
        return []


async def _search_with_duckduckgo(search_queries: list) -> list:
    """DuckDuckGo로 검색 (병렬 처리)"""
    if DDGS is None:
        logger.warning("DuckDuckGo 라이브러리 없음")
        return []
    
    logger.info(f"DuckDuckGo 검색 시작: {len(search_queries)}개 쿼리 (병렬 처리)")
    
    all_results = []
    seen_urls = set()
    
    # 모든 쿼리를 병렬로 처리
    tasks = [_search_single_ddg_query(query) for query in search_queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"DuckDuckGo 쿼리 오류 ({search_queries[i][:50]}): {result}")
            continue
        
        for item in result:
            url = item.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append({
                    "title": item.get("title", ""),
                    "body": item.get("body", ""),
                    "href": url,
                })
    
    logger.info(f"DuckDuckGo 검색 완료: {len(all_results)}개 결과 (병렬 처리)")
    return all_results


async def _search_single_tavily_query(query: str, tavily_api_key: str) -> list:
    """단일 Tavily 검색 쿼리 처리 (병렬 처리용)"""
    if not TAVILY_AVAILABLE or not tavily_api_key:
        return []
    
    try:
        # TavilyClient는 동기식이므로 별도 스레드에서 실행
        def _sync_search():
            client = TavilyClient(api_key=tavily_api_key)
            response = client.search(
                query=query,
                search_depth="basic",  # basic 또는 advanced
                max_results=config.MAX_RESULTS_PER_QUERY,
                include_answer=False,
                include_raw_content=False
            )
            return response.get("results", [])
        
        # 별도 스레드에서 실행
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            results = await loop.run_in_executor(executor, _sync_search)
        
        return results
        
    except Exception as e:
        logger.error(f"Tavily 쿼리 오류 ({query[:50]}): {e}")
        return []


async def _search_with_tavily(search_queries: list) -> list:
    """Tavily로 검색 (병렬 처리)"""
    tavily_api_key = config.TAVILY_API_KEY
    
    if not TAVILY_AVAILABLE:
        logger.warning("Tavily 라이브러리 없음")
        return []
    
    if not tavily_api_key:
        logger.warning("Tavily API 키가 설정되지 않음")
        return []
    
    logger.info(f"Tavily 검색 시작: {len(search_queries)}개 쿼리 (병렬 처리)")
    
    all_results = []
    seen_urls = set()
    
    # 모든 쿼리를 병렬로 처리
    tasks = [_search_single_tavily_query(query, tavily_api_key) for query in search_queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Tavily 쿼리 오류 ({search_queries[i][:50]}): {result}")
            continue
        
        for item in result:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("content", "") or item.get("snippet", ""),
                    "url": url,
                })
    
    logger.info(f"Tavily 검색 완료: {len(all_results)}개 결과 (병렬 처리)")
    return all_results


async def _get_price_from_api(coin_name: str, is_past_date: bool, requested_date):
    """시세 API에서 가격 정보 가져오기 (단일 코인)"""
    try:
        if is_past_date and requested_date:
            # 과거 날짜: CoinGecko 우선
            try:
                from ...coingecko import coingecko_service
                price_data = await coingecko_service.get_price(coin_name, convert="krw", target_date=requested_date)
                if price_data:
                    return price_data, "coingecko_api"
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"CoinGecko API 오류: {e}")
            
            # CoinMarketCap 시도
            try:
                from ...coinmarketcap import coinmarketcap_service
                price_data = await coinmarketcap_service.get_price(coin_name, convert="KRW", target_date=requested_date)
                if price_data:
                    return price_data, "coinmarketcap_api"
            except ImportError:
                pass
        else:
            # 현재 시세: CoinMarketCap
            try:
                from ...coinmarketcap import coinmarketcap_service
                price_data = await coinmarketcap_service.get_price(coin_name, convert="KRW", target_date=None)
                if price_data:
                    return price_data, "coinmarketcap_api"
            except ImportError:
                pass
    except Exception as e:
        logger.error(f"시세 API 오류: {e}")
    
    return None, None


async def _get_prices_from_api(coin_names: list, is_past_date: bool, requested_date):
    """시세 API에서 여러 코인의 가격 정보 가져오기 (병렬 처리)"""
    import asyncio
    
    if not coin_names:
        return []
    
    # 모든 코인을 병렬로 조회
    tasks = [_get_price_from_api(coin_name, is_past_date, requested_date) for coin_name in coin_names]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    price_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"코인 '{coin_names[i]}' 조회 실패: {result}")
            continue
        
        price_data, api_source = result
        if price_data:
            price_results.append((price_data, api_source, coin_names[i]))
    
    return price_results


def _extract_coin_names(user_message: str) -> list:
    """사용자 메시지에서 여러 코인명 추출 (리스트 반환)
    
    띄어쓰기 처리: "비트 코인" → "비트코인"으로 정규화
    """
    coin_names = []
    try:
        from ...coinmarketcap import coinmarketcap_service
        
        # 띄어쓰기 제거 버전도 체크 (예: "비트 코인" → "비트코인")
        normalized_message = user_message.replace(" ", "")
        
        # 한국어 코인명 추출 (모든 매칭)
        # 원본 메시지와 정규화된 메시지 모두 체크
        for coin_korean, coin_symbol in coinmarketcap_service.SYMBOL_MAPPING.items():
            # 원본 메시지에서 체크
            if coin_korean in user_message:
                if coin_korean not in coin_names:
                    coin_names.append(coin_korean)
            # 정규화된 메시지에서 체크 (띄어쓰기 제거)
            elif coin_korean in normalized_message:
                if coin_korean not in coin_names:
                    coin_names.append(coin_korean)
            # 역방향 체크: "비트 코인"에서 "비트코인" 찾기
            elif coin_korean.replace(" ", "") in normalized_message:
                if coin_korean not in coin_names:
                    coin_names.append(coin_korean)
        
        # 영어 심볼 추출 (모든 매칭)
        symbol_matches = re.findall(r'\b([A-Z]{2,5})\b', user_message.upper())
        for symbol in symbol_matches:
            # 알려진 심볼인지 확인
            if symbol in coinmarketcap_service.SYMBOL_MAPPING.values():
                # 심볼을 한국어명으로 변환
                for korean, eng_symbol in coinmarketcap_service.SYMBOL_MAPPING.items():
                    if eng_symbol == symbol and korean not in coin_names:
                        coin_names.append(korean)
                        break
        
        # 추가: 일반적인 코인명 패턴 체크 (예: "비트 코인", "이더 리움")
        common_patterns = {
            "비트 코인": "비트코인",
            "이더 리움": "이더리움",
            "리 플": "리플",
            "도지 코인": "도지코인",
            "솔 라나": "솔라나",
            "폴카 닷": "폴카닷",
            "체인 링크": "체인링크",
            "유니 스왑": "유니스왑",
            "아발란 체": "아발란체",
            "폴리 곤": "폴리곤",
        }
        for spaced_name, correct_name in common_patterns.items():
            if spaced_name in user_message and correct_name not in coin_names:
                coin_names.append(correct_name)
        
    except ImportError:
        pass
    
    return coin_names if coin_names else []


def _extract_date_from_message(message: str):
    """메시지에서 날짜 추출"""
    date_patterns = [
        r'(\d{4})-(\d{1,2})-(\d{1,2})',
        r'(\d{4})\.(\d{1,2})\.(\d{1,2})',
        r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, message)
        if match:
            year, month, day = map(int, match.groups())
            try:
                kst = timezone(timedelta(hours=9))
                return datetime(year, month, day, tzinfo=kst)
            except ValueError:
                continue
    
    return None


@traceable(name="researcher", run_type="chain")
async def researcher(state: ChatState):
    """Researcher: 웹 검색 수행"""
    print("="*60, file=sys.stdout, flush=True)
    print("Researcher 노드 시작: 웹 검색", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    ensure_logger_setup()
    logger.info("="*60)
    logger.info("Researcher 노드 시작")
    
    session_id = state.get("session_id", "default")
    search_queries = state.get("search_queries", [])
    current_messages = state.get("messages", [])
    user_messages = [msg for msg in current_messages if isinstance(msg, HumanMessage)]
    
    if not user_messages:
        return {
            "web_search_results": [],
            "session_id": session_id  # 세션 ID 명시적으로 포함
        }
    
    last_user_message = user_messages[-1].content
    msg_lower = last_user_message.lower()
    
    # 시세 질문 감지
    is_price_query = any(keyword in msg_lower for keyword in config.PRICE_KEYWORDS)
    
    # 맥락 기반 시세 질문 감지
    if not is_price_query and len(user_messages) > 1:
        for prev_msg in user_messages[-3:-1]:
            prev_content = prev_msg.content.lower() if hasattr(prev_msg, 'content') else str(prev_msg).lower()
            if any(keyword in prev_content for keyword in config.PRICE_KEYWORDS):
                coin_only_patterns = ['은?', '는?', '도?', '요?']
                if any(pattern in msg_lower for pattern in coin_only_patterns):
                    is_price_query = True
                    logger.info("✅ 맥락 기반 시세 질문 감지")
                    break
    
    # 날짜 추출
    requested_date = _extract_date_from_message(last_user_message)
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).date()
    is_past_date = requested_date and requested_date.date() < today
    
    # 365일 제한 확인 (CoinGecko 무료 플랜 제한)
    date_limit_exceeded = False
    if is_past_date and requested_date:
        days_diff = (today - requested_date.date()).days
        if days_diff > 365:
            date_limit_exceeded = True
            logger.info(f"⚠️ 365일 제한 초과: 요청 날짜가 {days_diff}일 전입니다.")
    
    # 시세 질문이면 API 우선 사용
    if is_price_query:
        logger.info("✅ 시세 질문 감지")
        print("[Researcher] ✅ 시세 질문 감지", file=sys.stdout, flush=True)
        
        coin_names = _extract_coin_names(last_user_message)
        
        if coin_names:
            logger.info(f"추출된 코인: {coin_names}")
            print(f"[Researcher] 추출된 코인: {', '.join(coin_names)}", file=sys.stdout, flush=True)
            
            # 365일 제한 초과 시 안내 메시지 반환
            if date_limit_exceeded:
                date_str = requested_date.strftime("%Y년 %m월 %d일") if requested_date else "해당 날짜"
                limit_message = {
                    "title": "과거 시세 조회 제한 안내",
                    "snippet": f"죄송합니다. 현재는 최근 365일 이내의 과거 시세만 조회할 수 있습니다.\n\n"
                              f"요청하신 날짜({date_str})는 현재로부터 365일을 초과하여 조회가 제한됩니다.\n\n"
                              f"더 오래된 과거 시세 조회 기능은 추후 지원 예정입니다. 양해 부탁드립니다.",
                    "url": "",
                    "source": "system_notice",
                    "score": 0.0,
                }
                logger.info("⚠️ 365일 제한 초과 - 사용자 안내 메시지 반환")
                print("[Researcher] ⚠️ 365일 제한 초과 - 안내 메시지 반환", file=sys.stdout, flush=True)
                return {
                    "web_search_results": [limit_message],
                    "session_id": session_id  # 세션 ID 명시적으로 포함
                }
            
            # 여러 코인 병렬 조회
            price_results = await _get_prices_from_api(coin_names, is_past_date, requested_date)
            
            if price_results:
                api_results = []
                date_info = f" ({requested_date.date()})" if is_past_date else ""
                
                for price_data, api_source, coin_name in price_results:
                    api_name = "CoinGecko" if "coingecko" in api_source else "CoinMarketCap"
                    
                    # 가격 표시 생성
                    if price_data.get('price_krw') and price_data.get('price_usd', 0) > 0:
                        price_display_str = f"💰 현재 가격: {price_data['price_krw']:,.0f}원 (${price_data['price_usd']:,.2f})"
                    elif price_data.get('price_krw'):
                        price_display_str = f"💰 현재 가격: {price_data['price_krw']:,.0f}원"
                    elif price_data.get('price_usd', 0) > 0:
                        price_display_str = f"💰 현재 가격: ${price_data['price_usd']:,.2f}"
                    else:
                        price_display_str = "💰 가격 정보 없음"
                    
                    snippet = f"{price_data['name']} ({price_data['symbol']}) 시세{date_info}:\n\n{price_display_str}"
                    
                    if price_data.get('price_change_24h') is not None:
                        snippet += f"\n📊 24시간 변동률: {price_data['price_change_24h']:+.2f}%"
                    if price_data.get('market_cap'):
                        snippet += f"\n💼 시가총액: ${price_data['market_cap']:,.0f}"
                    
                    snippet += f"\n🕐 업데이트: {price_data['last_updated']}"
                    snippet += f"\n\n출처: {api_name}"
                    
                    api_result = {
                        "title": f"{price_data['name']} 시세{date_info} - {api_name}",
                        "snippet": snippet.strip(),
                        "url": f"https://coinmarketcap.com/currencies/{price_data['name'].lower().replace(' ', '-')}/",
                        "source": api_source,
                        "score": 0.95,
                    }
                    
                    api_results.append(api_result)
                    logger.info(f"✅ {api_name} API 결과: {price_data['symbol']}")
                
                print(f"[Researcher] ✅ {len(api_results)}개 코인 시세 조회 완료", file=sys.stdout, flush=True)
                
                return {
                    "web_search_results": api_results,
                    "session_id": session_id  # 세션 ID 명시적으로 포함
                }
            else:
                logger.warning("⚠️ API 조회 실패 - 웹 검색으로 폴백")
        else:
            logger.warning("⚠️ 코인명 추출 실패 - 웹 검색으로 폴백")
    
    # 검색 쿼리 생성
    if not search_queries:
        kst = timezone(timedelta(hours=9))
        current_year = datetime.now(kst).year
        
        if any(keyword in msg_lower for keyword in ['이벤트', '프로모션']):
            search_queries = [
                f"빗썸 진행중인 이벤트 {current_year}",
                "빗썸 현재 프로모션",
                "빗썸 이벤트 공지사항"
            ]
        else:
            search_queries = [
                last_user_message,
                f"빗썸 {last_user_message}",
                f"{last_user_message} 빗썸"
            ]
    
    # 웹 검색 수행 (병렬 처리: Google, DuckDuckGo, Tavily 동시 실행)
    web_search_results = []
    
    # 이전 검색에서 Google API 할당량 초과 여부 확인
    google_rate_limit_hit = state.get("google_rate_limit_hit", False)
    
    if google_rate_limit_hit:
        logger.info("⚠️ 이전 검색에서 Google API 할당량 초과 감지 - Google 검색 건너뛰기")
        print("[Researcher] ⚠️ Google API 할당량 초과 - Google 검색 건너뛰기", file=sys.stdout, flush=True)
        google_results = []
        rate_limit_hit = True
        # DuckDuckGo와 Tavily만 실행
        duckduckgo_task = _search_with_duckduckgo(search_queries)
        tavily_task = _search_with_tavily(search_queries)
        
        results = await asyncio.gather(
            duckduckgo_task,
            tavily_task,
            return_exceptions=True
        )
        
        # DuckDuckGo 결과 처리
        if isinstance(results[0], Exception):
            logger.error(f"DuckDuckGo 검색 오류: {results[0]}")
            ddg_results = []
        else:
            ddg_results = results[0]
        
        # Tavily 결과 처리
        if isinstance(results[1], Exception):
            logger.error(f"Tavily 검색 오류: {results[1]}")
            tavily_results = []
        else:
            tavily_results = results[1]
    else:
        logger.info("🔀 병렬 검색 시작: Google + DuckDuckGo + Tavily 동시 실행")
        print("[Researcher] 🔀 병렬 검색 시작: Google + DuckDuckGo + Tavily", file=sys.stdout, flush=True)
        
        # Google, DuckDuckGo, Tavily 검색을 병렬로 실행
        google_task = _search_with_google(search_queries)
        duckduckgo_task = _search_with_duckduckgo(search_queries)
        tavily_task = _search_with_tavily(search_queries)
        
        results = await asyncio.gather(
            google_task,
            duckduckgo_task,
            tavily_task,
            return_exceptions=True
        )
        
        # Google 결과 처리
        if isinstance(results[0], Exception):
            logger.error(f"Google 검색 오류: {results[0]}")
            google_results = []
            rate_limit_hit = False
        else:
            google_results, rate_limit_hit = results[0]
        
        # DuckDuckGo 결과 처리
        if isinstance(results[1], Exception):
            logger.error(f"DuckDuckGo 검색 오류: {results[1]}")
            ddg_results = []
        else:
            ddg_results = results[1]
        
        # Tavily 결과 처리
        if isinstance(results[2], Exception):
            logger.error(f"Tavily 검색 오류: {results[2]}")
            tavily_results = []
        else:
            tavily_results = results[2]
    
    # Google 결과 추가
    if google_results:
        for i, result in enumerate(google_results[:config.MAX_SEARCH_RESULTS], 1):
            web_search_results.append({
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "url": result.get("url", ""),
                "rank": i,
                "source": "google"
            })
    
    if ddg_results:
        seen_urls = {r.get("url", "") for r in web_search_results}
        rank_offset = len(web_search_results)
        
        for i, result in enumerate(ddg_results[:config.MAX_SEARCH_RESULTS], 1):
            url = result.get("href", "") or result.get("url", "")
            if url and url not in seen_urls:
                web_search_results.append({
                    "title": result.get("title", ""),
                    "snippet": result.get("body", "") or result.get("snippet", ""),
                    "url": url,
                    "rank": rank_offset + i,
                    "source": "duckduckgo"
                })
    
    # Tavily 결과 추가
    if tavily_results:
        seen_urls = {r.get("url", "") for r in web_search_results}
        rank_offset = len(web_search_results)
        
        for i, result in enumerate(tavily_results[:config.MAX_SEARCH_RESULTS], 1):
            url = result.get("url", "")
            if url and url not in seen_urls:
                web_search_results.append({
                    "title": result.get("title", ""),
                    "snippet": result.get("snippet", ""),
                    "url": url,
                    "rank": rank_offset + i,
                    "source": "tavily"
                })
    
    # 검색 완료 메시지
    search_summary = f"[웹 검색 완료]\n{len(web_search_results)}개 결과"
    researcher_message = AIMessage(content=search_summary)
    
    print(f"[Researcher] 완료: {len(web_search_results)}개 결과", file=sys.stdout, flush=True)
    logger.info(f"Researcher 완료: {len(web_search_results)}개 결과")
    logger.info("="*60)
    print("="*60, file=sys.stdout, flush=True)
    
    search_loop_count = state.get("search_loop_count", 0) + 1
    
    # Google API 할당량 초과가 발생했으면 state에 저장 (다음 검색에서 Google 건너뛰기)
    if rate_limit_hit:
        logger.info("⚠️ Google API 할당량 초과 - 다음 검색에서 Google 건너뛰기")
    
    return {
        "web_search_results": web_search_results,
        "messages": current_messages + [researcher_message],
        "search_loop_count": search_loop_count,
        "google_rate_limit_hit": rate_limit_hit,  # Google API 할당량 초과 여부 저장
        "summarized_results": [],
        "session_id": session_id  # 세션 ID 명시적으로 포함
    }

