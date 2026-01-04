"""
Hybrid Specialist 노드 - FAQ + 웹 검색 조합
"""
import sys
import logging
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from ...models import ChatState, QuestionType
from ...configuration import config
from ...vector_store import vector_store
from ...utils import (
    ensure_logger_setup,
    extract_user_message,
)

logger = logging.getLogger(__name__)


def _get_writer_llm():
    """Writer LLM 인스턴스 생성"""
    return ChatOpenAI(**config.get_writer_llm_config())


@traceable(name="hybrid_specialist", run_type="chain")
async def hybrid_specialist(state: ChatState):
    """Hybrid Specialist: FAQ + 웹 검색 조합"""
    print("="*60, file=sys.stdout, flush=True)
    print("Hybrid Specialist 시작: FAQ + 웹 검색", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    ensure_logger_setup()
    logger.info("Hybrid Specialist 시작")
    
    user_message = extract_user_message(state)
    db_results = state.get("db_search_results", [])
    
    # FAQ 검색 (아직 안 했다면)
    if not db_results:
        try:
            db_results = await vector_store.search(user_message, limit=3)
            logger.info(f"FAQ 검색 완료: {len(db_results)}개 결과")
        except Exception as e:
            logger.error(f"FAQ 검색 실패: {e}")
    
    # FAQ 결과로 답변 생성
    if db_results:
        context = "\n".join([f"[FAQ {i+1}]\n{result.get('text', '')}" for i, result in enumerate(db_results[:3])])
        
        hybrid_prompt = f"""
다음 FAQ 정보를 바탕으로 사용자 질문에 답변하세요.
추가로 최신 정보가 필요할 수 있으므로, FAQ 정보와 함께 일반적인 안내도 포함하세요.

사용자 질문: {user_message}

FAQ 정보:
{context}

답변 규칙:
1. FAQ 정보를 바탕으로 답변
2. 최신 정보가 필요할 수 있음을 안내
3. 빗썸 공식 홈페이지에서 확인 가능하다고 안내
4. 친절하고 이해하기 쉽게 설명
"""
        
        try:
            writer_llm = _get_writer_llm()
            response = await writer_llm.ainvoke([HumanMessage(content=hybrid_prompt)])
            response_text = response.content if hasattr(response, "content") else str(response)
            
            logger.info("Hybrid Specialist 완료 (FAQ 기반)")
            print("="*60, file=sys.stdout, flush=True)
            
            return {
                "messages": [AIMessage(content=response_text)],
                "db_search_results": db_results
            }
        except Exception as e:
            logger.error(f"Hybrid 답변 생성 실패: {e}")
    
    # FAQ 결과가 없으면 웹 검색으로 전환
    logger.info("FAQ 결과 없음, 웹 검색으로 전환")
    return {
        "needs_web_search": True,
        "question_type": QuestionType.WEB_SEARCH
    }

