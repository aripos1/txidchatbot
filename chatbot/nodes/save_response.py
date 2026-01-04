"""
Save Response 노드 - 응답을 MongoDB에 저장
"""
from langchain_core.messages import HumanMessage, AIMessage

from ..models import ChatState
from ..mongodb_client import mongodb_client


async def save_response(state: ChatState):
    """응답을 MongoDB에 저장"""
    session_id = state.get("session_id", "default")
    messages = state.get("messages", [])
    
    if messages:
        # 사용자 메시지 저장
        user_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
        if user_messages:
            last_user_msg = user_messages[-1]
            await mongodb_client.save_message(
                session_id=session_id,
                role="user",
                content=last_user_msg.content
            )
        
        # AI 응답 저장
        ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
        if ai_messages:
            last_ai_msg = ai_messages[-1]
            await mongodb_client.save_message(
                session_id=session_id,
                role="assistant",
                content=last_ai_msg.content
            )
    
    # 상태 정보 보존
    return state

