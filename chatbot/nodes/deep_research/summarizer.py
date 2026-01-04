"""
Summarizer 노드 - 검색 결과 요약
"""
import logging
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from ...models import ChatState
from ...configuration import config
from ...utils import ensure_logger_setup

logger = logging.getLogger(__name__)


def _get_summarization_llm():
    """Summarization LLM 인스턴스 생성"""
    return ChatOpenAI(**config.get_summarization_llm_config())


@traceable(name="summarizer", run_type="llm")
async def summarizer(state: ChatState):
    """Summarizer: 검색 결과 요약"""
    ensure_logger_setup()
    logger.info("Summarizer 노드 시작")
    
    web_search_results = state.get("web_search_results", [])
    current_messages = state.get("messages", [])
    
    logger.info(f"입력 검색 결과: {len(web_search_results)}개")
    
    # 사용자 질문 추출
    user_query = ""
    user_messages = [msg for msg in current_messages if isinstance(msg, HumanMessage)]
    if user_messages:
        user_query = user_messages[-1].content
    
    # 정확한 데이터가 필요한 질문은 요약 건너뛰기
    precise_data_keywords = ['시세', '가격', '가치', '비용', '수수료', '환율', '%', '원', '달러']
    user_query_lower = user_query.lower() if user_query else ""
    needs_precise_data = any(keyword in user_query_lower for keyword in precise_data_keywords)
    
    if needs_precise_data:
        logger.info("정확한 데이터 필요 - 요약 건너뛰기")
        return {
            "summarized_results": web_search_results,
            "messages": current_messages
        }
    
    # 요약이 비활성화되어 있거나 결과가 적으면 건너뛰기
    if not config.ENABLE_SUMMARIZATION or len(web_search_results) < config.SUMMARIZATION_THRESHOLD:
        logger.info(f"요약 건너뛰기: {len(web_search_results)}개 < {config.SUMMARIZATION_THRESHOLD}")
        return {
            "summarized_results": web_search_results,
            "messages": current_messages
        }
    
    try:
        logger.info(f"검색 결과 요약 시작: {len(web_search_results)}개")
        
        search_results_text = []
        for i, result in enumerate(web_search_results, 1):
            title = result.get('title', '제목 없음')
            snippet = result.get('snippet', '')
            url = result.get('url', '')
            search_results_text.append(
                f"[결과 {i}]\n"
                f"제목: {title}\n"
                f"내용: {snippet[:500]}\n"
                f"출처: {url}\n"
            )
        
        summarization_prompt = f"""
다음은 사용자 질문에 대한 웹 검색 결과입니다. 핵심 정보만 추출해주세요.

사용자 질문: {user_query}

검색 결과:
{chr(10).join(search_results_text[:20])}

요약 규칙:
1. 중복된 정보 제거
2. 핵심 정보만 추출 (이벤트명, 기간, 혜택 등)
3. 출처 URL 유지
4. 한국어로 간결하게

각 결과를 2-3줄로 요약하세요.
"""
        
        summarization_llm = _get_summarization_llm()
        response = await summarization_llm.ainvoke([HumanMessage(content=summarization_prompt)])
        summary_text = response.content if hasattr(response, "content") else str(response)
        
        summarized_results = []
        for i, result in enumerate(web_search_results, 1):
            summarized_results.append({
                "title": result.get('title', ''),
                "snippet": summary_text,
                "url": result.get('url', ''),
                "rank": result.get('rank', i),
                "original_snippet": result.get('snippet', '')
            })
        
        logger.info(f"✅ 요약 완료: {len(summarized_results)}개")
        logger.info("="*60)
        
        return {
            "summarized_results": summarized_results,
            "messages": current_messages
        }
    except Exception as e:
        logger.error(f"요약 실패: {e}, 원본 사용")
        return {
            "summarized_results": web_search_results,
            "messages": current_messages
        }

