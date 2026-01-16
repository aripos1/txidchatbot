"""
Grader 노드 - 검색 결과 평가
"""
import os
import re
import sys
import logging
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from ...models import ChatState, GraderResult
from ...configuration import config
from ...utils import ensure_logger_setup

logger = logging.getLogger(__name__)


def _get_grader_llm():
    """Grader LLM 인스턴스 생성"""
    grader_model = os.getenv("GRADER_MODEL") or os.getenv("OPENAI_MODEL") or config._DEFAULT_MODEL
    grader_temperature = float(os.getenv("GRADER_TEMPERATURE", "0.1"))
    logger.info(f"🤖 Grader 모델: {grader_model}, Temperature: {grader_temperature}")
    return ChatOpenAI(
        model=grader_model,
        temperature=grader_temperature,
        openai_api_key=config.OPENAI_API_KEY
    )


@traceable(name="grader", run_type="llm")
async def grader(state: ChatState):
    session_id = state.get("session_id", "default")
    """Grader: 검색 결과 평가"""
    print("="*60, file=sys.stdout, flush=True)
    print("Grader 노드 시작: 검색 결과 평가", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    ensure_logger_setup()
    logger.info("="*60)
    logger.info("Grader 노드 시작")
    
    web_search_results = state.get("web_search_results", [])
    current_messages = state.get("messages", [])
    search_loop_count = state.get("search_loop_count", 0)
    
    # 사용자 질문 추출
    user_query = ""
    user_messages = [msg for msg in current_messages if isinstance(msg, HumanMessage)]
    if user_messages:
        user_query = user_messages[-1].content
    
    logger.info(f"검색 결과: {len(web_search_results)}개, 반복: {search_loop_count}회")
    
    # 검색 결과 없으면 불합격
    if not web_search_results:
        logger.warning("검색 결과 없음 - 불합격")
        return {
            "grader_score": 0.0,
            "grader_feedback": "검색 결과가 없습니다.",
            "is_sufficient": False,
            "session_id": session_id  # 세션 ID 명시적으로 포함
        }
    
    # 시스템 안내 메시지 자동 합격 (365일 제한 등)
    has_system_notice = any(
        result.get("source") == "system_notice"
        for result in web_search_results
    )
    
    if has_system_notice:
        logger.info("✅ 시스템 안내 메시지 - 자동 합격")
        print("[Grader] ✅ 시스템 안내 메시지 - 자동 합격", file=sys.stdout, flush=True)
        notice_result = next((r for r in web_search_results if r.get("source") == "system_notice"), None)
        notice_text = notice_result.get("snippet", "시스템 안내 메시지") if notice_result else "시스템 안내"
        return {
            "grader_score": 0.9,
            "session_id": session_id,  # 세션 ID 명시적으로 포함
            "grader_feedback": notice_text,
            "is_sufficient": True
        }
    
    # 시세 API 결과 자동 합격
    api_sources = {"coinmarketcap_api", "coingecko_api"}
    has_api_result = any(
        result.get("source") in api_sources 
        for result in web_search_results
    )
    
    if has_api_result:
        logger.info("✅ 시세 API 결과 - 자동 합격")
        print("[Grader] ✅ 시세 API 결과 - 자동 합격", file=sys.stdout, flush=True)
        return {
            "grader_score": 0.95,
            "grader_feedback": "시세 API에서 정확한 가격 정보를 가져왔습니다.",
            "is_sufficient": True,
            "session_id": session_id  # 세션 ID 명시적으로 포함
        }
    
    # 검색 결과 텍스트 변환
    search_results_text = []
    for i, result in enumerate(web_search_results[:10], 1):
        title = result.get('title', '제목 없음')
        snippet = result.get('snippet', '')
        url = result.get('url', '')
        search_results_text.append(
            f"[결과 {i}]\n"
            f"제목: {title}\n"
            f"내용: {snippet}\n"
            f"출처: {url}\n"
        )
    
    # 시세/가격 질문 숫자 포함 체크
    needs_price_number = any(keyword in user_query.lower() for keyword in [
        '시세', '가격', '현재가', 'price', '시장가', '얼마', '원', '달러'
    ])
    
    has_number_in_results = False
    if needs_price_number and web_search_results:
        price_patterns = [
            r'\d+[,.]?\d*\s*(원|달러|USD|KRW|BTC|ETH|₩|\$)',
            r'\d+[,.]?\d*\s*(만원|억원)',
            r'\$\d+[,.]?\d*',
            r'\d{1,3}(?:,\d{3})+(?:\.\d+)?',
            r'\d+\.?\d*\s*%',
        ]
        
        all_results_text = ' '.join([
            result.get('title', '') + ' ' + result.get('snippet', '')
            for result in web_search_results[:10]
        ])
        
        for pattern in price_patterns:
            if re.findall(pattern, all_results_text, re.IGNORECASE):
                has_number_in_results = True
                break
        
        if not has_number_in_results:
            large_numbers = re.findall(r'\b\d{4,}\b', all_results_text)
            if large_numbers:
                has_number_in_results = True
    
    # 비교 질문 감지
    is_comparison_query = any(keyword in user_query.lower() for keyword in [
        '비교', '차이', '변화', '변동', '상승', '하락'
    ])
    
    additional_instructions = ""
    if needs_price_number:
        additional_instructions += "\n**중요**: 시세/가격 질문입니다. 숫자가 없으면 불합격."
    if is_comparison_query:
        additional_instructions += "\n**비교 질문**: 부분 정보라도 0.6 이상."
    
    # Google API 할당량 초과 여부 확인
    google_rate_limit_hit = state.get("google_rate_limit_hit", False)
    google_note = ""
    if google_rate_limit_hit:
        google_note = "\n**참고**: Google 검색이 할당량 초과로 사용되지 않았습니다. DuckDuckGo와 Tavily 결과만으로 평가하세요."
    
    grader_prompt = f"""
당신은 검색 결과 평가 전문가입니다.

**사용자 질문:**
{user_query}

**검색 결과:**
{chr(10).join(search_results_text)}
{google_note}

**평가 기준:**
1. 질문에 직접 답변 가능한 정보 포함?
2. 구체적인 숫자/날짜/이름 포함?
3. 신뢰할 수 있는 출처? (Google이 없어도 DuckDuckGo/Tavily 결과가 충분하면 합격)
4. 최신 정보?

**점수:**
- 0.6 이상: 충분 (답변 가능) - DuckDuckGo/Tavily 결과만으로도 충분하면 합격
- 0.6 미만: 부족 (재검색 필요)
{additional_instructions}

한국어로 피드백 작성.
"""
    
    try:
        grader_llm = _get_grader_llm()
        grader_result = await grader_llm.with_structured_output(GraderResult).ainvoke(
            [HumanMessage(content=grader_prompt)]
        )
        
        # 시세 질문인데 숫자 없으면 점수 하향
        if needs_price_number and not has_number_in_results:
            if grader_result.score > 0.5:
                logger.warning(f"⚠️ 숫자 없어 점수 조정: {grader_result.score:.2f} -> 0.4")
                grader_result.score = 0.4
                grader_result.is_sufficient = False
                grader_result.feedback += " [숫자 없음으로 점수 조정]"
        
        print(f"[Grader] ✅ 평가 완료: 점수 {grader_result.score:.2f}", file=sys.stdout, flush=True)
        logger.info(f"✅ 평가: 점수 {grader_result.score:.2f}, 충분: {grader_result.is_sufficient}")
        logger.info("="*60)
        print("="*60, file=sys.stdout, flush=True)
        
        return {
            "grader_score": grader_result.score,
            "grader_feedback": grader_result.feedback,
            "is_sufficient": grader_result.is_sufficient,
            "session_id": session_id  # 세션 ID 명시적으로 포함
        }
    except Exception as e:
        logger.error(f"Grader 오류: {e}")
        return {
            "grader_score": 0.6 if web_search_results else 0.0,
            "grader_feedback": f"평가 오류: {str(e)}",
            "is_sufficient": len(web_search_results) > 0,
            "session_id": session_id  # 세션 ID 명시적으로 포함
        }

