"""
Planner 노드 - 연구 계획 수립 및 검색 쿼리 생성
"""
import sys
import logging
import difflib
from datetime import datetime, timezone, timedelta
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from ...models import ChatState, SearchPlan
from ...configuration import config
from ...utils import ensure_logger_setup

logger = logging.getLogger(__name__)


def _get_planner_llm():
    """Planner LLM 인스턴스 생성"""
    return ChatOpenAI(**config.get_planner_llm_config())


@traceable(name="planner", run_type="llm")
async def planner(state: ChatState):
    """Planner: 연구 계획 수립 및 검색 쿼리 생성"""
    print("="*60, file=sys.stdout, flush=True)
    print("Planner 노드 시작: 검색 계획 수립", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    ensure_logger_setup()
    logger.info("="*60)
    logger.info("Planner 노드 시작: 검색 계획 수립")
    
    current_messages = state.get("messages", [])
    user_messages = [msg for msg in current_messages if isinstance(msg, HumanMessage)]
    
    if not user_messages:
        logger.warning("Planner: 사용자 메시지 없음")
        return {"research_plan": "", "search_queries": []}
    
    last_user_message = user_messages[-1].content
    logger.info(f"사용자 질문: {last_user_message[:100]}...")
    
    # 현재 연도 및 전일 날짜
    kst = timezone(timedelta(hours=9))
    current_datetime = datetime.now(kst)
    current_year = current_datetime.year
    
    yesterday_datetime = current_datetime - timedelta(days=1)
    yesterday_date_str = yesterday_datetime.strftime("%Y년 %m월 %d일")
    yesterday_date_iso = yesterday_datetime.strftime("%Y-%m-%d")
    
    # 재검색 안내
    search_loop_count = state.get("search_loop_count", 0)
    grader_feedback = state.get("grader_feedback", "")
    previous_queries = state.get("search_queries", [])
    
    user_query_lower = last_user_message.lower()
    is_realtime_info = any(keyword in user_query_lower for keyword in [
        '시세', '가격', '현재가', 'price', '시장가'
    ])
    is_bithumb_faq = any(keyword in user_query_lower for keyword in [
        '빗썸', 'bithumb', '출금', '입금', '이벤트', '프로모션'
    ]) and not is_realtime_info
    
    retry_guidance = ""
    if search_loop_count > 1:
        retry_guidance = f"""
**재검색 안내 (이전 검색 {search_loop_count-1}회 시도):**
이전 검색 쿼리: {', '.join(previous_queries[:3]) if previous_queries else '없음'}
피드백: {grader_feedback if grader_feedback else '이전 검색 결과가 충분하지 않았습니다.'}

**중요**: 이전 검색 쿼리와 다른 접근 방식을 시도하세요.
"""
    
    query_prompt = f"""
사용자의 질문에 대한 최적의 웹 검색 쿼리를 생성해주세요.

**현재 날짜 정보**
- 현재 연도: {current_year}년
- 오늘 날짜: {current_datetime.strftime('%Y년 %m월 %d일')}

사용자 질문: {last_user_message}

{retry_guidance}

**질문 유형:**
- 실시간 정보: {"예" if is_realtime_info else "아니오"}
- 빗썸 FAQ: {"예" if is_bithumb_faq else "아니오"}

**검색 쿼리 생성 규칙:**
1. 5-7개 쿼리 생성
2. 한국어 우선, 영어 1-2개
3. {current_year}년 키워드 사용
4. 빗썸 FAQ는 site:support.bithumb.com/hc/ko 우선

한국어로 간단명료하게 작성하세요.
"""
    
    try:
        planner_llm = _get_planner_llm()
        search_plan = await planner_llm.with_structured_output(SearchPlan).ainvoke(
            [HumanMessage(content=query_prompt)]
        )
        
        raw_queries = search_plan.search_queries[:config.MAX_SEARCH_QUERIES]
        search_queries = []
        
        if is_realtime_info:
            search_queries = raw_queries[:]
            logger.info("실시간 정보 질문: 사이트 제한 없이 검색")
        elif is_bithumb_faq:
            keywords = [w for w in user_query_lower.split() if w not in ['빗썸', 'bithumb', '에', '의', '을', '를'] and len(w) >= 2]
            core_keywords = ' '.join(keywords[:5])
            
            if core_keywords:
                support_query = f"site:support.bithumb.com/hc/ko {core_keywords}"
                if support_query not in search_queries:
                    search_queries.append(support_query)
            
            for query in raw_queries:
                query_lower = query.lower()
                if 'support.bithumb.com' in query_lower:
                    search_queries.append(query)
                elif 'site:bithumb.com' not in query_lower:
                    search_queries.append(f"site:bithumb.com {query}")
                else:
                    search_queries.append(query)
            
            logger.info("빗썸 FAQ 질문: 고객지원 페이지 우선")
        else:
            search_queries = raw_queries[:]
        
        search_queries = list(dict.fromkeys(search_queries))[:config.MAX_SEARCH_QUERIES]
        
        # 재검색 다양성 검증
        if search_loop_count > 1 and previous_queries:
            max_similarity = 0.0
            for new_query in search_queries:
                for prev_query in previous_queries:
                    similarity = difflib.SequenceMatcher(None, new_query.lower(), prev_query.lower()).ratio()
                    max_similarity = max(max_similarity, similarity)
            
            if max_similarity > 0.8:
                logger.warning(f"⚠️ 재검색 쿼리가 이전과 너무 유사 (유사도: {max_similarity:.2f})")
            else:
                logger.info(f"✅ 재검색 쿼리 다양성 확인 (최대 유사도: {max_similarity:.2f})")
        
        research_plan = search_plan.research_plan
        
        print(f"[Planner] ✅ 검색 계획 수립 완료: 쿼리 {len(search_queries)}개", file=sys.stdout, flush=True)
        logger.info(f"✅ 검색 계획 수립 완료: {len(search_queries)}개 쿼리")
        logger.info("="*60)
        print("="*60, file=sys.stdout, flush=True)
        
        return {
            "research_plan": research_plan,
            "search_queries": search_queries
        }
    except Exception as e:
        logger.error(f"Planner 오류, fallback 사용: {e}")
        msg_lower = last_user_message.lower()
        if any(keyword in msg_lower for keyword in ['이벤트', '프로모션']):
            default_queries = [
                f"빗썸 진행중인 이벤트 {current_year}",
                "빗썸 현재 프로모션",
                "빗썸 이벤트 공지사항"
            ]
        else:
            default_queries = [
                last_user_message,
                f"빗썸 {last_user_message}",
                f"{last_user_message} 빗썸"
            ]
        return {
            "research_plan": "웹 검색을 통해 관련 정보를 찾습니다.",
            "search_queries": default_queries[:config.MAX_SEARCH_QUERIES]
        }

