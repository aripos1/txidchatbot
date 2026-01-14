"""
Save Response 노드 - 응답을 MongoDB에 저장
"""
import sys
import logging
from langchain_core.messages import HumanMessage, AIMessage

from ..models import ChatState
from ..mongodb_client import mongodb_client

logger = logging.getLogger(__name__)


async def save_response(state: ChatState):
    """응답을 MongoDB에 저장"""
    logger.info("="*60)
    logger.info("💾 Save Response: MongoDB에 저장 중")
    print("="*60, file=sys.stdout, flush=True)
    print("💾 Save Response: MongoDB에 저장 중", file=sys.stdout, flush=True)
    
    session_id = state.get("session_id", "default")
    messages = state.get("messages", [])
    
    logger.info(f"💾 Save Response - session_id: {session_id}")
    print(f"💾 Save Response - session_id: {session_id}", file=sys.stdout, flush=True)
    
    # 세션 ID가 "default"이면 저장하지 않음 (스트리밍 완료 후 저장 로직에서 처리)
    if session_id == "default":
        logger.warning("⚠️ Save Response: session_id가 'default'입니다. 저장하지 않습니다. (스트리밍 완료 후 저장 로직에서 처리됨)")
        print("⚠️ Save Response: session_id가 'default'입니다. 저장하지 않습니다.", file=sys.stdout, flush=True)
        return state
    
    saved_count = 0
    
    if messages:
        # AI 응답만 저장 (사용자 메시지는 요청 받자마자 이미 저장됨)
        ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
        if ai_messages:
            last_ai_msg = ai_messages[-1]
            content = last_ai_msg.content if hasattr(last_ai_msg, "content") else str(last_ai_msg)
            
            if content and content.strip():
                try:
                    logger.info(f"💾 AI 응답 저장 시도 - session_id: {session_id}, role: assistant, content 길이: {len(content)}")
                    result = await mongodb_client.save_message(
                        session_id=session_id,
                        role="assistant",
                        content=content
                    )
                    if result:
                        saved_count += 1
                        logger.info(f"✅ AI 응답 저장 완료 (session_id: {session_id}, 길이: {len(content)}자, ID: {result})")
                        print(f"✅ AI 응답 저장 완료 (session_id: {session_id}, 길이: {len(content)}자)", file=sys.stdout, flush=True)
                    else:
                        logger.warning(f"⚠️ AI 응답 저장 실패 (반환값 없음, session_id: {session_id}, 길이: {len(content)}자)")
                        print(f"⚠️ AI 응답 저장 실패 (반환값 없음, session_id: {session_id})", file=sys.stdout, flush=True)
                except Exception as e:
                    logger.error(f"❌ AI 응답 저장 중 오류 발생 (session_id: {session_id}): {e}", exc_info=True)
                    print(f"❌ AI 응답 저장 중 오류 발생 (session_id: {session_id}): {e}", file=sys.stdout, flush=True)
            else:
                logger.warning("⚠️ AI 응답 내용이 비어있어 저장하지 않음")
    
    logger.info(f"💾 Save Response 완료: {saved_count}개 메시지 저장")
    logger.info("="*60)
    print(f"💾 Save Response 완료: {saved_count}개 메시지 저장", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    # 상태 정보 보존 (session_id 명시적으로 포함)
    return {
        **state,
        "session_id": session_id  # 세션 ID 명시적으로 포함
    }

