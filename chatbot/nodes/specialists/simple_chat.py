"""
SimpleChat Specialist 노드 - 단순 대화 처리
"""
import sys
import logging
from datetime import datetime, timezone, timedelta
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from ...models import ChatState
from ...configuration import config
from ...utils import (
    ensure_logger_setup,
    extract_user_message,
    extract_conversation_context,
    handle_node_error,
)

logger = logging.getLogger(__name__)


def _get_writer_llm():
    """Writer LLM 인스턴스 생성"""
    return ChatOpenAI(**config.get_writer_llm_config())


@traceable(name="simple_chat_specialist", run_type="llm")
async def simple_chat_specialist(state: ChatState):
    """SimpleChat Specialist: 단순 대화 처리"""
    print("="*60, file=sys.stdout, flush=True)
    print("SimpleChat Specialist 시작", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    ensure_logger_setup()
    logger.info("SimpleChat Specialist 시작")
    
    session_id = state.get("session_id", "default")
    user_message = extract_user_message(state)
    
    # 대화 맥락 추출 (이전 답변 제외 - 사용자 질문만 포함)
    conversation_context = extract_conversation_context(state, limit=3, include_ai_responses=False)
    has_context = bool(conversation_context)
    
    # 맥락 의존적 질문 감지
    context_dependent_keywords = ['자세하게', '자세히', '더', '그것', '그거', '그', '이것', '이거', '이', '알려줘', '설명해줘']
    is_context_dependent = any(keyword in user_message for keyword in context_dependent_keywords)
    
    # 맥락 의존적 질문이고 이전 대화가 있으면 이전 질문과 결합
    if is_context_dependent and has_context:
        logger.info("SimpleChat: 맥락 의존적 질문 감지 - 이전 대화 맥락 활용")
        previous_messages = state.get("messages", [])
        prev_user_msg = None
        for msg in reversed(previous_messages[:-1]):
            if isinstance(msg, HumanMessage):
                prev_user_msg = msg.content
                break
        
        if prev_user_msg:
            combined_message = f"{prev_user_msg} {user_message}"
            logger.info(f"이전 질문과 결합: {prev_user_msg[:50]}... + {user_message[:50]}...")
            user_message_for_response = combined_message
        else:
            user_message_for_response = user_message
    else:
        user_message_for_response = user_message
    
    # 현재 날짜/시간 정보 (한국 시간)
    kst = timezone(timedelta(hours=9))
    current_datetime = datetime.now(kst)
    current_date_str = current_datetime.strftime("%Y년 %m월 %d일")
    current_date_iso = current_datetime.strftime("%Y-%m-%d")
    current_time_str = current_datetime.strftime("%H시 %M분")
    
    # 대화 맥락 섹션
    context_section = ""
    if has_context and conversation_context:
        context_section = f"""

**대화 맥락:**
{conversation_context}

위 대화 맥락을 반드시 고려하여 답변하세요.
"""
    
    # 사용자 입력을 프롬프트에서 완전히 제거하고, 시스템 메시지로만 전달
    system_message = f"""당신은 블록체인과 빗썸 이용 방법에 대하여 도와주는 친절한 챗봇입니다.
사용자의 인사나 감사 표현, 또는 일반적인 질문에 자연스럽고 친절하게 응답하세요.

**중요: 현재 날짜/시간 정보**
- 현재 날짜: {current_date_str} ({current_date_iso})
- 현재 시간: {current_time_str}
{context_section}

**절대적으로 중요한 규칙:**
1. 사용자 입력을 그대로 반복하지 마세요. 예를 들어:
   - ❌ 잘못된 응답: "아년 ㅇ" (사용자 입력 그대로 반복)
   - ❌ 잘못된 응답: "반가워요!" (사용자 입력 "반가워"를 변형만 한 것)
   - ✅ 올바른 응답: "안녕하세요! 반갑습니다. 오늘 하루도 좋은 하루 되세요!" (완전히 새로운 문장)
   - ✅ 올바른 응답: "반가워요! 오늘 하루도 좋은 일 가득하길 바랍니다." (사용자 입력을 포함하지 않음)

2. 사용자 입력의 단어나 문장을 그대로 사용하지 말고, 의미를 바탕으로 완전히 새로운 문장으로 응답하세요.

3. 친절하고 자연스러운 톤 유지
4. 간결하게 응답 (1-2문장)
5. 날짜/시간 관련 질문이면 위의 현재 날짜/시간 정보를 사용하여 정확하게 답변
6. 필요시 블록체인 또는 빗썸 이용 방법 안내 가능
7. 한국어로 답변
8. **절대 학습 데이터의 날짜를 사용하지 말고, 반드시 위에 제공된 현재 날짜를 사용하세요**
"""
    
    simple_chat_prompt = f"""{system_message}

사용자가 다음과 같이 말했습니다. 이 입력을 반복하지 말고, 의미를 이해한 후 완전히 새로운 문장으로 직접 응답하세요:
{user_message_for_response}"""
    
    try:
        writer_llm = _get_writer_llm()
        # 시스템 메시지와 사용자 메시지를 분리하여 전달
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=f"사용자: {user_message_for_response}")
        ]
        response = await writer_llm.ainvoke(messages)
        response_text = response.content if hasattr(response, "content") else str(response)
        
        logger.info("SimpleChat Specialist 완료")
        print("="*60, file=sys.stdout, flush=True)
        
        return {
            "messages": [AIMessage(content=response_text)],
            "session_id": session_id  # 세션 ID 명시적으로 포함
        }
    except Exception as e:
        return handle_node_error(e, "simple_chat_specialist", state)

