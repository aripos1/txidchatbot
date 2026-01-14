"""
Router Agent - 질문 분류 및 라우팅을 담당하는 에이전트
"""
import logging
import sys
from typing import List, Optional
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from .base_agent import BaseAgent
from ..models import ChatState, QuestionType, RoutingDecision
from ..configuration import config
from ..utils import (
    ensure_logger_setup,
    extract_user_message,
    extract_conversation_context,
    detect_transaction_hash,
    handle_node_error,
)
from ..nodes.router import RuleBasedClassifier

logger = logging.getLogger(__name__)


class RouterAgent(BaseAgent):
    """Router Agent - 질문 분류 및 적절한 에이전트로 라우팅"""
    
    def __init__(self):
        super().__init__(
            name="RouterAgent",
            description="사용자 질문을 분석하고 적절한 전문가 에이전트로 라우팅하는 에이전트"
        )
        self.update_state(
            routing_count=0,
            routing_decisions={}
        )
    
    async def process(self, state: ChatState) -> ChatState:
        """라우팅 처리 로직 (기존 router 함수 로직 포함)"""
        print("="*60, file=sys.stdout, flush=True)
        print("RouterAgent 시작: 질문 분류 및 라우팅", file=sys.stdout, flush=True)
        print("="*60, file=sys.stdout, flush=True)
        
        ensure_logger_setup()
        logger.info("="*60)
        logger.info("RouterAgent 시작: 질문 분류 및 라우팅")
        
        self.update_state(routing_count=self.get_state("routing_count", 0) + 1)
        
        user_message = extract_user_message(state)
        if not user_message:
            logger.warning("RouterAgent: 사용자 메시지 없음")
            return {
                "routing_decision": None,
                "question_type": QuestionType.GENERAL,
                "specialist_used": "faq"
            }
        
        logger.info(f"사용자 질문: {user_message[:100]}...")
        
        # 규칙 기반 분류 시도
        rule_result, context_info = RuleBasedClassifier.classify(state, user_message)
        if rule_result:
            result = rule_result
        else:
            # LLM 기반 분류 (애매한 경우)
            user_message_for_classification = context_info["user_message_for_classification"]
            has_context = context_info["has_context"]
            conversation_context = extract_conversation_context(state, limit=3)
            
            context_section = ""
            if has_context:
                context_section = f"""
**중요: 대화 맥락**
이전 대화 내용:
{conversation_context}

위 대화 맥락을 반드시 고려하여 분류하세요.
"""
            
            routing_prompt = f"""
사용자 질문을 분석하여 적절한 전문가로 라우팅하세요.

사용자 질문: {user_message_for_classification}
{context_section}

전문가 유형:
1. simple_chat: 단순 대화, 인사, 감사 표현
2. faq: FAQ 데이터베이스에서 답변 가능한 질문
3. transaction: **트랜잭션 해시(TXID) 조회 요청만**
4. web_search: 실시간 정보, 이벤트, 프로모션 등 최신 정보 필요
5. hybrid: FAQ에서 답변 가능하지만 최신 정보도 필요한 경우

한국어로 reasoning을 작성하세요.
"""
            
            try:
                router_llm = self._get_router_llm()
                routing_decision = await router_llm.with_structured_output(RoutingDecision).ainvoke(
                    [HumanMessage(content=routing_prompt)]
                )
                
                print(f"[RouterAgent] ✅ 질문 분류 완료: {routing_decision.question_type.value} (신뢰도: {routing_decision.confidence:.2f})", file=sys.stdout, flush=True)
                logger.info(f"✅ 질문 분류 완료: {routing_decision.question_type.value}")
                
                # 모호한 질문 감지
                is_ambiguous = (
                    routing_decision.confidence < 0.6 or
                    routing_decision.needs_clarification or
                    routing_decision.question_type == QuestionType.GENERAL
                )
                
                if is_ambiguous:
                    logger.info("⚠️ 모호한 질문 감지 - Intent Clarifier로 라우팅")
                    result = {
                        "routing_decision": routing_decision,
                        "question_type": QuestionType.INTENT_CLARIFICATION,
                        "needs_clarification": True,
                        "specialist_used": "intent_clarifier"
                    }
                else:
                    logger.info("="*60)
                    print("="*60, file=sys.stdout, flush=True)
                    
                    result = {
                        "routing_decision": routing_decision,
                        "question_type": routing_decision.question_type,
                        "needs_web_search": routing_decision.needs_web_search,
                        "faq_threshold": 0.75 if routing_decision.question_type == QuestionType.FAQ else 0.7,
                        "specialist_used": routing_decision.suggested_specialist,
                        "needs_clarification": False
                    }
                    
                    # 트랜잭션 타입인 경우 해시 설정
                    if routing_decision.question_type == QuestionType.TRANSACTION:
                        logger.info(f"트랜잭션 질문 감지. 사용자 메시지 전체 길이: {len(user_message)}자")
                        logger.info(f"사용자 메시지 처음 100자: {user_message[:100]}")
                        detected_hash = detect_transaction_hash(user_message)
                        if detected_hash:
                            result["transaction_hash"] = detected_hash
                            logger.info(f"✅ 트랜잭션 해시 감지: {detected_hash} (길이: {len(detected_hash)}자)")
                        else:
                            logger.warning(f"트랜잭션 해시 추출 실패. 사용자 메시지: {user_message[:200]}")
            except Exception as e:
                error_result = handle_node_error(e, "router_agent", state, log_level="error")
                result = {
                    **error_result,
                    "routing_decision": None,
                    "question_type": QuestionType.GENERAL,
                    "specialist_used": "faq",
                    "faq_threshold": 0.7,
                    "needs_clarification": False
                }
        
        # 라우팅 결정 기록
        question_type = result.get("question_type")
        specialist_used = result.get("specialist_used")
        
        if question_type:
            routing_decisions = self.get_state("routing_decisions", {})
            question_type_str = question_type.value if hasattr(question_type, 'value') else str(question_type)
            routing_decisions[question_type_str] = routing_decisions.get(question_type_str, 0) + 1
            self.update_state(routing_decisions=routing_decisions)
        
        # 멀티 에이전트: 다른 에이전트에게 라우팅 정보 공유
        if specialist_used:
            routing_decision = result.get("routing_decision")
            confidence = routing_decision.confidence if routing_decision else None
            
            # 라우팅된 에이전트에게 정보 공유
            target_agent_name = None
            if specialist_used == "faq":
                target_agent_name = "FAQAgent"
            elif specialist_used == "transaction":
                target_agent_name = "TransactionAgent"
            elif specialist_used == "simple_chat":
                target_agent_name = "SimpleChatAgent"
            elif specialist_used == "web_search":
                target_agent_name = "PlannerAgent"
            
            if target_agent_name:
                try:
                    # 정보 공유 (비동기이지만 그래프가 다음 노드를 호출하므로 여기서는 정보만 공유)
                    await self.share_info(
                        target_agent_name,
                        {
                            "question_type": question_type_str,
                            "confidence": confidence,
                            "routing_decision": routing_decision.dict() if routing_decision else None,
                            "user_message": user_message
                        },
                        result
                    )
                    logger.info(f"📨 [{self.name}] → [{target_agent_name}]: 라우팅 정보 공유 (질문 유형: {question_type_str}, 신뢰도: {confidence:.2f})")
                    print(f"📨 [{self.name}] → [{target_agent_name}]: 라우팅 정보 공유", file=sys.stdout, flush=True)
                except Exception as e:
                    logger.warning(f"⚠️ 에이전트 정보 공유 실패: {e}")
            
            self.record_interaction(
                specialist_used,
                "route",
                {
                    "question_type": question_type_str,
                    "confidence": confidence
                }
            )
        
        # ⚠️ 중요: 원본 state와 result를 병합하여 반환 (messages 보존)
        return {**state, **result}
    
    def _get_router_llm(self):
        """Router LLM 인스턴스 생성"""
        import os
        router_model = os.getenv("ROUTER_MODEL") or os.getenv("OPENAI_MODEL") or config._DEFAULT_MODEL
        return ChatOpenAI(
            model=router_model,
            temperature=0.1,
            openai_api_key=config.OPENAI_API_KEY
        )
    
    def can_handle(self, state: ChatState) -> bool:
        """Router는 항상 처리 가능 (엔트리 포인트)"""
        return True
    
    def get_capabilities(self) -> List[str]:
        return [
            "규칙 기반 분류",
            "LLM 기반 분류",
            "트랜잭션 해시 감지",
            "시세/가격 질문 감지",
            "이벤트/프로모션 감지",
            "FAQ 질문 감지",
            "단순 대화 감지",
            "의도 명확화 필요 감지",
            "에이전트 라우팅"
        ]
    
    def get_routing_statistics(self) -> dict:
        """라우팅 통계 반환"""
        return {
            "total_routings": self.get_state("routing_count", 0),
            "routing_decisions": self.get_state("routing_decisions", {}),
            "interaction_history": self.interaction_history
        }


# 에이전트 인스턴스 생성 (싱글톤 패턴)
_router_agent = None


def get_router_agent() -> RouterAgent:
    """Router 에이전트 인스턴스 가져오기"""
    global _router_agent
    if _router_agent is None:
        _router_agent = RouterAgent()
    return _router_agent


# 기존 코드 호환성을 위한 래퍼 함수
# 주의: 이 함수는 chatbot/nodes/__init__.py에서 import되어 사용됩니다.
async def router(state: ChatState) -> ChatState:
    """기존 코드 호환성을 위한 래퍼"""
    agent = get_router_agent()
    return await agent(state)
