"""
CheckDB 노드 - FAQ 검색 (벡터 DB)
"""
import sys
import logging
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable

from ...models import ChatState
from ...configuration import config
from ...mongodb_client import mongodb_client
from ...vector_store import vector_store
from ...utils import ensure_logger_setup

logger = logging.getLogger(__name__)


@traceable(name="check_db", run_type="chain")
async def check_db(state: ChatState):
    """CheckDB: FAQ 검색 (벡터 DB에서 검색)"""
    print("="*60, file=sys.stdout, flush=True)
    print("CheckDB 노드 시작: 벡터 DB 검색", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    ensure_logger_setup()
    
    session_id = state.get("session_id", "default")
    
    # MongoDB에서 대화 기록 가져오기
    history = await mongodb_client.get_conversation_history(session_id, limit=10)
    
    # BaseMessage 형식으로 변환
    history_messages = []
    for msg in history:
        if msg.get("role") == "user":
            history_messages.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("role") == "assistant":
            history_messages.append(AIMessage(content=msg.get("content", "")))
    
    # 새로운 사용자 메시지 추출
    current_messages = state.get("messages", [])
    new_user_messages = [msg for msg in current_messages if isinstance(msg, HumanMessage)]
    
    # 벡터 DB에서 검색
    search_results = []
    needs_deep_research = True
    
    logger.info("="*60)
    logger.info("CheckDB 노드 시작: 벡터 DB 검색")
    print(f"[CheckDB] 사용자 메시지: {new_user_messages[-1].content[:50] if new_user_messages else 'None'}...", file=sys.stdout, flush=True)
    
    if new_user_messages:
        last_user_message = new_user_messages[-1].content
        logger.info(f"사용자 질문: {last_user_message[:100]}...")
        
        try:
            logger.info("벡터 DB 검색 시작...")
            search_results = await vector_store.search(last_user_message, limit=3)
            logger.info(f"벡터 DB 검색 완료: {len(search_results)}개 결과 발견")
            
            if search_results:
                for idx, result in enumerate(search_results, 1):
                    score = result.get("score", 0.0)
                    print(f"[CheckDB] 결과 {idx}: 점수 {score:.4f} (임계값: {config.SIMILARITY_THRESHOLD:.2f})", file=sys.stdout, flush=True)
                    logger.info(f"  결과 {idx}: 점수 {score:.4f}")
            
            if search_results and search_results[0].get("score", 0) > config.SIMILARITY_THRESHOLD:
                needs_deep_research = False
                logger.info(f"✅ DB에서 충분한 정보 발견 - Deep Research 불필요")
            else:
                logger.info("❌ DB 검색 결과 부족 - Deep Research 필요")
                
        except Exception as e:
            logger.error(f"벡터 검색 실패: {e}", exc_info=True)
    
    print(f"[CheckDB] 노드 완료: Deep Research 필요 = {needs_deep_research}", file=sys.stdout, flush=True)
    logger.info(f"CheckDB 노드 완료")
    logger.info("="*60)
    print("="*60, file=sys.stdout, flush=True)
    
    return {
        "db_search_results": search_results,
        "needs_deep_research": needs_deep_research,
        "messages": history_messages + new_user_messages
    }

