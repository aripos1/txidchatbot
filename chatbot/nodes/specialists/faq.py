"""
FAQ Specialist 노드 - FAQ 벡터 DB 검색 및 답변
"""
import re
import sys
import logging
import asyncio
from datetime import datetime, timezone, timedelta
import httpx
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from ...models import ChatState, QuestionType
from ...configuration import config
from ...vector_store import vector_store
from ...utils import (
    ensure_logger_setup,
    extract_user_message,
    extract_conversation_context,
    handle_node_error,
)

# 선택적 의존성 (DuckDuckGo)
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

logger = logging.getLogger(__name__)


def _get_writer_llm():
    """Writer LLM 인스턴스 생성"""
    return ChatOpenAI(**config.get_writer_llm_config())


async def _search_db(search_message: str, user_message: str) -> list:
    """하이브리드 검색: 벡터 DB 검색 + 키워드 검색"""
    try:
        def extract_keywords(text):
            keywords = []
            text_lower = text.lower()
            
            if '100만원' in text or '100만' in text:
                keywords.append('100만원')
            elif '만원' in text:
                amount_match = re.search(r'(\d+만원)', text)
                if amount_match:
                    keywords.append(amount_match.group(1))
            
            if '미만' in text:
                keywords.append('미만')
            elif '이상' in text:
                keywords.append('이상')
            
            if '출금' in text:
                keywords.append('출금')
            elif '입금' in text:
                keywords.append('입금')
            
            if '주소록' in text or '주소' in text:
                keywords.append('주소록')
            
            return keywords
        
        search_queries = [search_message]
        
        user_msg_lower = search_message.lower()
        is_withdrawal = any(keyword in user_msg_lower for keyword in ['출금', '입금', '송금', '이체'])
        is_krw_withdrawal = (
            '원화' in user_msg_lower or 
            '원' in user_msg_lower or 
            '한국돈' in user_msg_lower or
            'krw' in user_msg_lower
        ) and is_withdrawal
        
        if is_withdrawal and not is_krw_withdrawal:
            if '주소록' not in user_msg_lower and '주소' not in user_msg_lower:
                keywords = extract_keywords(search_message)
                if keywords:
                    compact_query = ' '.join(keywords) + ' 주소록'
                    if compact_query != search_message:
                        search_queries.append(compact_query)
        
        search_queries = [q[:100] for q in search_queries if len(q) <= 100]
        
        all_results = []
        seen_texts = set()
        
        # 하이브리드 검색 사용 (벡터 + 키워드)
        final_limit = config.FINAL_TOP_K
        
        for query in search_queries[:2]:
            try:
                # 하이브리드 검색 수행 (가중치 결합 방식 사용)
                results = await vector_store.hybrid_search(query, limit=final_limit, use_rrf=False)
                for result in results:
                    result_text = result.get('text', '')
                    if result_text and result_text not in seen_texts:
                        seen_texts.add(result_text)
                        all_results.append(result)
            except Exception as e:
                logger.warning(f"쿼리 '{query[:50]}...' 하이브리드 검색 실패, 벡터 검색으로 대체: {e}")
                # 하이브리드 검색 실패 시 벡터 검색으로 대체
                try:
                    results = await vector_store.search(query, limit=final_limit)
                    for result in results:
                        result_text = result.get('text', '')
                        if result_text and result_text not in seen_texts:
                            seen_texts.add(result_text)
                            all_results.append(result)
                except Exception as fallback_error:
                    logger.warning(f"쿼리 '{query[:50]}...' 벡터 검색도 실패: {fallback_error}")
                    continue
        
        # 점수 기준으로 정렬 (하이브리드 검색 결과는 이미 정렬되어 있지만, 여러 쿼리 결과를 합칠 때 다시 정렬)
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        final_results = all_results[:final_limit]
        
        logger.info(f"FAQ 하이브리드 검색 완료: {len(final_results)}개 결과")
        return final_results
    except Exception as e:
        logger.error(f"FAQ DB 검색 실패: {e}")
        return []


async def _search_support_page(search_message: str, user_message: str) -> list:
    """빗썸 고객지원 페이지 검색"""
    try:
        google_api_key = config.GOOGLE_API_KEY
        google_cx = config.GOOGLE_CX
        
        if not google_api_key or not google_cx:
            logger.debug("Google API 설정 없음 - 고객지원 페이지 검색 건너뛰기")
            return []
        
        search_keywords = search_message.split()[:5]
        core_query = ' '.join(search_keywords)
        
        support_site_queries = [
            f"site:support.bithumb.com/hc/ko {core_query}",
            f"site:support.bithumb.com/hc/ko {search_message}",
            f"site:support.bithumb.com {core_query}",
            f"site:bithumb.com {core_query} 고객지원"
        ]
        
        support_site_queries = list(dict.fromkeys([q[:100] for q in support_site_queries if len(q) <= 100]))
        
        support_results = []
        rate_limit_hit = False
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for query in support_site_queries[:3]:
                if rate_limit_hit:
                    break
                try:
                    url = config.GOOGLE_SEARCH_API_URL
                    params = {
                        "key": google_api_key,
                        "cx": google_cx,
                        "q": query,
                        "num": 5,
                        "lr": "lang_ko",
                    }
                    
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        if "items" in data:
                            for item in data.get("items", []):
                                url_link = item.get("link", "")
                                if url_link and "bithumb.com" in url_link:
                                    is_support_page = "support.bithumb.com" in url_link.lower()
                                    support_results.append({
                                        "title": item.get("title", ""),
                                        "snippet": item.get("snippet", ""),
                                        "url": url_link,
                                        "text": f"{item.get('title', '')}\n{item.get('snippet', '')}",
                                        "source": "bithumb_support",
                                        "score": 0.9 if is_support_page else 0.6
                                    })
                    elif response.status_code == 429:
                        logger.warning("Google API 할당량 초과 - DuckDuckGo로 전환")
                        rate_limit_hit = True
                        break
                    
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.warning(f"빗썸 고객지원 페이지 검색 실패: {e}")
                    continue
        
        # Google API 실패 시 DuckDuckGo로 fallback
        if rate_limit_hit or not support_results:
            if DDGS is not None:
                logger.info("DuckDuckGo로 빗썸 고객지원 페이지 검색 시도")
                try:
                    # DuckDuckGo는 site: 연산자를 잘 지원하지 않으므로, 키워드 기반 검색으로 변경
                    # "빗썸 고객지원" + 질문 키워드 조합
                    search_keywords = search_message.split()[:3]  # 핵심 키워드만 추출
                    core_keywords = ' '.join(search_keywords)
                    
                    duckduckgo_queries = [
                        f"빗썸 고객지원 {core_keywords}",
                        f"빗썸 support.bithumb.com {core_keywords}",
                        f"빗썸 {user_message[:50]}",  # 사용자 메시지 일부 사용
                    ]
                    
                    with DDGS() as ddgs:
                        for query in duckduckgo_queries[:3]:
                            try:
                                results = list(ddgs.text(query, max_results=5))
                                logger.info(f"DuckDuckGo 검색 쿼리: '{query}' -> {len(results)}개 결과")
                                
                                for result in results:
                                    url_link = result.get("href", "")
                                    title = result.get("title", "")
                                    
                                    # support.bithumb.com/hc/ko 페이지 우선 필터링
                                    if url_link and "bithumb.com" in url_link:
                                        is_support_page = "support.bithumb.com" in url_link.lower()
                                        is_hc_ko_page = "/hc/ko" in url_link.lower()
                                        
                                        # 중복 제거
                                        if not any(r.get("url") == url_link for r in support_results):
                                            logger.info(f"  - 발견: {title[:50]}... | URL: {url_link}")
                                            
                                            # support.bithumb.com/hc/ko 페이지는 최고 점수
                                            if is_hc_ko_page:
                                                score = 0.95
                                            elif is_support_page:
                                                score = 0.85
                                            else:
                                                score = 0.6
                                            
                                            support_results.append({
                                                "title": title,
                                                "snippet": result.get("body", ""),
                                                "url": url_link,
                                                "text": f"{title}\n{result.get('body', '')}",
                                                "source": "bithumb_support",
                                                "score": score
                                            })
                            except Exception as e:
                                logger.warning(f"DuckDuckGo 검색 쿼리 실패: {e}")
                                continue
                except Exception as e:
                    logger.warning(f"DuckDuckGo 검색 실패: {e}")
        
        # support.bithumb.com/hc/ko 페이지 우선 정렬
        hc_ko_results = [r for r in support_results if "/hc/ko" in r.get("url", "").lower()]
        support_page_results = [r for r in support_results if "support.bithumb.com" in r.get("url", "").lower() and "/hc/ko" not in r.get("url", "").lower()]
        other_results = [r for r in support_results if "support.bithumb.com" not in r.get("url", "").lower()]
        
        # 우선순위: /hc/ko > support.bithumb.com > 기타
        final_results = hc_ko_results + support_page_results + other_results
        
        # 점수 기준으로 정렬 (높은 점수 우선)
        final_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        final_results = final_results[:5]  # 상위 5개만 반환
        
        # 로그에 실제 URL 출력
        if final_results:
            logger.info(f"빗썸 고객지원 페이지 검색 완료: {len(final_results)}개 결과")
            for i, result in enumerate(final_results[:3], 1):
                url = result.get("url", "")
                title = result.get("title", "")[:50]
                is_hc_ko = "/hc/ko" in url.lower()
                logger.info(f"  [{i}] {'✅ /hc/ko' if is_hc_ko else '⚠️ 기타'}: {title}... | {url}")
        else:
            logger.warning("빗썸 고객지원 페이지 검색 결과 없음")
        
        return final_results
    except Exception as e:
        logger.warning(f"빗썸 고객지원 페이지 검색 중 오류: {e}")
        return []


@traceable(name="faq_specialist", run_type="chain")
async def faq_specialist(state: ChatState):
    """FAQ Specialist: FAQ 벡터 DB 검색 및 답변"""
    print("="*60, file=sys.stdout, flush=True)
    print("FAQ Specialist 시작", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    ensure_logger_setup()
    logger.info("FAQ Specialist 시작")
    
    session_id = state.get("session_id", "default")
    user_message = extract_user_message(state)
    faq_threshold = state.get("faq_threshold", 0.7)
    
    # 대화 맥락 추출
    conversation_context = extract_conversation_context(state, limit=5)
    has_context = bool(conversation_context)
    
    # 맥락 의존적 질문 처리
    context_dependent_keywords = ['자세하게', '자세히', '더', '그것', '그거', '알려줘', '설명해줘']
    is_context_dependent = any(keyword in user_message for keyword in context_dependent_keywords)
    
    if is_context_dependent and has_context:
        logger.info("맥락 의존적 질문 감지: 이전 대화 맥락을 활용하여 검색")
        previous_messages = state.get("messages", [])
        prev_user_msg = None
        
        if len(previous_messages) >= 2:
            for msg in reversed(previous_messages[:-1]):
                if isinstance(msg, HumanMessage):
                    prev_user_msg = msg.content
                    break
        
        if prev_user_msg:
            combined_message = f"{prev_user_msg} {user_message}"
            search_message = combined_message
        else:
            search_message = user_message
    else:
        search_message = user_message
    
    # 현재 날짜/시간 정보
    kst = timezone(timedelta(hours=9))
    current_datetime = datetime.now(kst)
    current_date_str = current_datetime.strftime("%Y년 %m월 %d일")
    current_date_iso = current_datetime.strftime("%Y-%m-%d")
    current_time_str = current_datetime.strftime("%H시 %M분")
    
    # 날짜/시간 질문 감지
    date_time_keywords = ['날짜', '날자', '일자', '오늘', '시간', '지금', '현재', '어제', '내일']
    msg_lower = user_message.lower()
    is_date_time_query = any(keyword in msg_lower for keyword in date_time_keywords)
    
    # 날짜/시간 질문은 직접 답변
    if is_date_time_query:
        yesterday_datetime = current_datetime - timedelta(days=1)
        yesterday_date_str = yesterday_datetime.strftime("%Y년 %m월 %d일")
        tomorrow_datetime = current_datetime + timedelta(days=1)
        tomorrow_date_str = tomorrow_datetime.strftime("%Y년 %m월 %d일")
        
        faq_prompt = f"""
사용자의 날짜/시간 관련 질문에 답변하세요.

**현재 날짜/시간 정보**
- 현재 날짜: {current_date_str} ({current_date_iso})
- 현재 시간: {current_time_str}
- 어제 날짜: {yesterday_date_str}
- 내일 날짜: {tomorrow_date_str}

사용자 질문: {user_message}

친절하고 정확하게 답변하세요.
"""
        try:
            writer_llm = _get_writer_llm()
            response = await writer_llm.ainvoke([HumanMessage(content=faq_prompt)])
            response_text = response.content if hasattr(response, "content") else str(response)
            
            logger.info("FAQ Specialist 완료 (날짜/시간 직접 답변)")
            print("="*60, file=sys.stdout, flush=True)
            
            return {
                "messages": [AIMessage(content=response_text)],
                "db_search_results": [],
                "session_id": session_id  # 세션 ID 명시적으로 포함
            }
        except Exception as e:
            logger.error(f"날짜/시간 답변 생성 실패: {e}")
            return {
                "messages": [AIMessage(content=f"오늘 날짜는 {current_date_str}입니다.")],
                "session_id": session_id  # 세션 ID 명시적으로 포함
            }
    
    # DB 검색
    db_results = await _search_db(search_message, user_message)
    db_best_score = db_results[0].get("score", 0) if db_results else 0
    logger.info(f"FAQ DB 검색 결과 점수: {db_best_score:.4f}")
    
    has_good_db_results = db_best_score > faq_threshold
    
    # 웹 검색
    support_results = await _search_support_page(search_message, user_message)
    web_best_score = max([r.get("score", 0) for r in support_results], default=0) if support_results else 0
    
    logger.info(f"점수 비교 - DB: {db_best_score:.4f} vs 웹: {web_best_score:.4f}")
    
    # 빗썸 고객지원 페이지 결과 우선 사용
    if support_results:
        logger.info(f"✅ 빗썸 고객지원 페이지 검색 결과 우선 사용 ({len(support_results)}개)")
        
        primary_results = support_results[:5]
        secondary_results = db_results[:3] if db_results else []
        
        context_parts = []
        context_parts.append("=== 빗썸 고객지원 페이지 검색 결과 ===\n")
        context_parts.append("\n".join([
            f"[검색 결과 {i+1}]\n{result.get('text', result.get('snippet', ''))}" 
            for i, result in enumerate(primary_results)
        ]))
        
        if secondary_results:
            context_parts.append(f"\n\n=== FAQ DB 검색 결과 (보조) ===\n")
            context_parts.append("\n".join([
                f"[FAQ {i+1}]\n{result.get('text', '')}" 
                for i, result in enumerate(secondary_results)
            ]))
        
        context_parts.append(f"\n\n=== 빗썸 고객지원 페이지 링크 ===\n")
        context_parts.append(f"**정확한 링크**: {config.BITHUMB_SUPPORT_URL}")
        context_parts.append("\n" + config.get_link_rules_prompt())
        
        context = "\n".join(context_parts)
        
        context_section = ""
        if has_context and conversation_context:
            context_section = f"""
**대화 맥락:**
{conversation_context}
"""
        
        faq_prompt = f"""
다음 빗썸 고객지원 페이지 검색 결과와 FAQ DB 정보를 바탕으로 사용자 질문에 답변하세요.

**현재 날짜/시간 정보**
- 현재 날짜: {current_date_str} ({current_date_iso})
- 현재 시간: {current_time_str}

사용자 질문: {user_message}
{context_section}

빗썸 고객지원 페이지 검색 결과 및 FAQ 정보:
{context}

답변 규칙:
1. 빗썸 고객지원 페이지 검색 결과를 우선적으로 참고
2. 출금 관련 질문의 경우, 원화 출금과 가상자산 출금을 구분하세요
3. 빗썸 고객지원 페이지 링크를 포함: {config.BITHUMB_SUPPORT_URL}
4. **번호 매기기 규칙 (매우 중요)**:
   - 여러 항목을 나열할 때는 반드시 순차적인 번호를 사용하세요 (1. 2. 3. 4. 5. ...)
   - 절대로 중첩 번호를 사용하지 마세요 (예: 1.1.1, 1.1.2, 2.1.1 ❌)
   - 절대로 하위 번호를 사용하지 마세요 (예: 1.1, 1.2, 2.1 ❌)
   - 번호는 1부터 시작하여 순차적으로 증가해야 합니다 (1. 2. 3. ✅)
5. 친절하고 이해하기 쉽게 설명
6. 한국어로 답변
"""
        
        try:
            writer_llm = _get_writer_llm()
            response = await writer_llm.ainvoke([HumanMessage(content=faq_prompt)])
            response_text = response.content if hasattr(response, "content") else str(response)
            
            logger.info("FAQ Specialist 완료")
            print("="*60, file=sys.stdout, flush=True)
            
            return {
                "messages": [AIMessage(content=response_text)],
                "db_search_results": support_results + (db_results or []),
                "search_queries": [search_message],  # 검색 쿼리 정보 추가
                "session_id": session_id  # 세션 ID 명시적으로 포함
            }
        except Exception as e:
            return handle_node_error(e, "faq_specialist", state)
    
    elif db_results and has_good_db_results:
        logger.info(f"✅ DB 결과 사용 (점수: {db_best_score:.4f})")
        
        context = "\n".join([f"[FAQ {i+1}]\n{result.get('text', '')}" for i, result in enumerate(db_results[:3])])
        
        faq_prompt = f"""
다음 FAQ 정보를 바탕으로 사용자 질문에 답변하세요.

**현재 날짜/시간 정보**
- 현재 날짜: {current_date_str} ({current_date_iso})
- 현재 시간: {current_time_str}

사용자 질문: {user_message}

FAQ 정보:
{context}

답변 규칙:
1. FAQ 정보를 바탕으로 정확하게 답변
2. 친절하고 이해하기 쉽게 설명
3. 빗썸 고객지원 페이지 링크를 포함: {config.BITHUMB_SUPPORT_URL}
4. 한국어로 답변
"""
        
        try:
            writer_llm = _get_writer_llm()
            response = await writer_llm.ainvoke([HumanMessage(content=faq_prompt)])
            response_text = response.content if hasattr(response, "content") else str(response)
            
            logger.info("FAQ Specialist 완료 (DB 결과 사용)")
            print("="*60, file=sys.stdout, flush=True)
            
            return {
                "messages": [AIMessage(content=response_text)],
                "db_search_results": db_results,
                "search_queries": [search_message],  # 검색 쿼리 정보 추가
                "session_id": session_id  # 세션 ID 명시적으로 포함
            }
        except Exception as e:
            return handle_node_error(e, "faq_specialist", state)
    
    else:
        logger.info("❌ 검색 결과 부족 - Hybrid로 위임")
        print("="*60, file=sys.stdout, flush=True)
        return {
            "db_search_results": [],
            "needs_web_search": True,
            "question_type": QuestionType.HYBRID,
            "session_id": session_id  # 세션 ID 명시적으로 포함
        }

