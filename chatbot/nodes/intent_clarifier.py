"""
Intent Clarifier 노드 - 모호한 질문의 의도 명확화
"""
import sys
import logging
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable
from pydantic import BaseModel, Field
from typing import List, Optional

from ..models import ChatState, QuestionType
from ..configuration import config
from ..utils import (
    ensure_logger_setup,
    extract_user_message,
    extract_conversation_context,
    handle_node_error,
)

logger = logging.getLogger(__name__)


class IntentClarification(BaseModel):
    """의도 명확화 결과"""
    needs_clarification: bool = Field(description="명확화가 필요한지 여부")
    clarification_question: Optional[str] = Field(default=None, description="명확화를 위한 질문")
    possible_intents: List[str] = Field(default_factory=list, description="가능한 의도 목록")
    suggested_intent: Optional[str] = Field(default=None, description="가장 가능성 높은 의도")


def _get_router_llm():
    """Router LLM 인스턴스 생성"""
    import os
    router_model = os.getenv("ROUTER_MODEL") or os.getenv("OPENAI_MODEL") or config._DEFAULT_MODEL
    return ChatOpenAI(
        model=router_model,
        temperature=0.1,
        openai_api_key=config.OPENAI_API_KEY
    )


@traceable(name="intent_clarifier", run_type="llm")
async def intent_clarifier(state: ChatState):
    """Intent Clarifier: 모호한 질문의 의도를 명확히 하기 위해 사용자에게 질문"""
    print("="*60, file=sys.stdout, flush=True)
    print("Intent Clarifier 시작: 의도 명확화", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    ensure_logger_setup()
    logger.info("="*60)
    logger.info("Intent Clarifier 시작: 의도 명확화")
    
    user_message = extract_user_message(state)
    if not user_message:
        logger.warning("Intent Clarifier: 사용자 메시지 없음")
        return {"messages": [AIMessage(content="질문을 다시 말씀해 주시겠어요?")]}
    
    # 대화 맥락 추출
    conversation_context = extract_conversation_context(state, limit=5)
    has_context = bool(conversation_context)
    
    context_section = ""
    if has_context:
        context_section = f"""
**이전 대화 맥락:**
{conversation_context}

위 대화 맥락을 고려하여 사용자의 의도를 파악하세요.
"""
    
    clarification_prompt = f"""
사용자의 질문이 모호하거나 여러 가지 의미로 해석될 수 있습니다. 사용자의 의도를 명확히 하기 위해 적절한 질문을 생성하세요.

**사용자 질문:**
{user_message}
{context_section}

**가능한 의도 유형:**
1. FAQ 질문: 출금, 입금, 수수료, 한도, 방법 등 빗썸 이용 방법
2. 시세/가격 질문: 비트코인, 이더리움 등 암호화폐 가격 정보
3. 트랜잭션 조회: 특정 트랜잭션 해시 조회
4. 이벤트/공지사항: 진행중인 이벤트, 프로모션, 공지사항
5. 일반 정보: 날짜, 시간 등 일반 정보

**명확화 질문 생성 규칙:**
1. 사용자의 질문을 분석하여 가능한 의도들을 파악하세요
2. 가능한 의도가 2개 이상이면, 사용자에게 선택할 수 있는 질문을 하세요
3. 질문은 친절하고 명확하게 작성하세요
4. 예시:
   - "비트코인"만 말한 경우: "비트코인에 대해 어떤 정보를 원하시나요? (시세 확인 / 거래 방법 / 트랜잭션 조회 등)"
   - "100만원"만 말한 경우: "100만원과 관련하여 무엇을 도와드릴까요? (출금 방법 / 입금 방법 / 수수료 확인 등)"

한국어로 명확화 질문을 작성하세요.
"""
    
    try:
        router_llm = _get_router_llm()
        clarification_result = await router_llm.with_structured_output(IntentClarification).ainvoke(
            [HumanMessage(content=clarification_prompt)]
        )
        
        if clarification_result.needs_clarification:
            clarification_question = clarification_result.clarification_question
            if not clarification_question:
                # 가능한 의도들을 나열하여 질문 생성
                if clarification_result.possible_intents:
                    intents_text = "\n".join([f"{i+1}. {intent}" for i, intent in enumerate(clarification_result.possible_intents)])
                    clarification_question = f"""질문이 명확하지 않아 정확히 답변드리기 어렵습니다. 

다음 중 어떤 것을 원하시나요?
{intents_text}

번호를 선택하시거나, 더 구체적으로 말씀해 주시면 도와드리겠습니다."""
                else:
                    clarification_question = "질문을 더 구체적으로 말씀해 주시겠어요? 예를 들어, 어떤 정보를 원하시는지 알려주시면 정확히 도와드릴 수 있습니다."
            
            logger.info(f"명확화 질문 생성: {clarification_question[:100]}...")
            print(f"[Intent Clarifier] 명확화 질문 생성", file=sys.stdout, flush=True)
            logger.info("="*60)
            print("="*60, file=sys.stdout, flush=True)
            
            return {"messages": [AIMessage(content=clarification_question)]}
        else:
            # 명확화 불필요 - 제안된 의도로 처리
            suggested_intent = clarification_result.suggested_intent
            logger.info(f"명확화 불필요 - 제안된 의도: {suggested_intent}")
            print(f"[Intent Clarifier] 명확화 불필요 - 제안된 의도: {suggested_intent}", file=sys.stdout, flush=True)
            
            # 제안된 의도로 다시 라우팅
            if suggested_intent == "faq":
                return {
                    "question_type": QuestionType.FAQ,
                    "specialist_used": "faq",
                    "needs_clarification": False
                }
            elif suggested_intent == "web_search":
                return {
                    "question_type": QuestionType.WEB_SEARCH,
                    "specialist_used": "web_search",
                    "needs_clarification": False
                }
            else:
                return {
                    "question_type": QuestionType.GENERAL,
                    "specialist_used": "faq",
                    "needs_clarification": False
                }
    except Exception as e:
        fallback_question = "질문을 더 구체적으로 말씀해 주시겠어요? 예를 들어:\n- 출금/입금 방법\n- 암호화폐 시세\n- 트랜잭션 조회\n- 이벤트/공지사항\n등을 알려주시면 정확히 도와드릴 수 있습니다."
        error_result = handle_node_error(e, "intent_clarifier", state, fallback_message=fallback_question)
        return {
            **error_result,
            "needs_clarification": False
        }

