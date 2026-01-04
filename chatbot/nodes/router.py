"""
Router 노드 - 질문 분류 및 라우팅 결정
규칙 기반 분류 + LLM 기반 분류
"""
import sys
import logging
from typing import Optional
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from ..models import ChatState, QuestionType, RoutingDecision
from ..configuration import config
from ..utils import (
    ensure_logger_setup,
    extract_user_message,
    extract_conversation_context,
    detect_transaction_hash,
    handle_node_error,
)

logger = logging.getLogger(__name__)


class RuleBasedClassifier:
    """규칙 기반 분류 서브 에이전트 (체인 패턴)"""
    
    @staticmethod
    def analyze_context(state: ChatState, user_message: str) -> dict:
        """맥락 분석: 대화 맥락 추출 및 맥락 의존적 질문 감지"""
        conversation_context = extract_conversation_context(state, limit=3)
        has_context = bool(conversation_context)
        
        if has_context:
            logger.info(f"대화 맥락 감지: 이전 대화 {len(state.get('messages', []))}개 메시지")
        
        # 맥락 의존적 질문 감지
        context_dependent_keywords = config.CONTEXT_DEPENDENT_KEYWORDS
        is_context_dependent = any(keyword in user_message for keyword in context_dependent_keywords)
        
        # 독립적인 질문 키워드 확인
        independent_question_keywords = config.INDEPENDENT_QUESTION_KEYWORDS
        has_independent_keyword = any(keyword in user_message for keyword in independent_question_keywords)
        
        # 맥락 결합 로직
        user_message_for_classification = user_message
        if is_context_dependent and has_context and not has_independent_keyword:
            logger.info("맥락 의존적 질문 감지: 이전 대화 맥락을 고려하여 분류")
            previous_messages = state.get("messages", [])
            if len(previous_messages) >= 2:
                prev_user_msg = None
                for msg in reversed(previous_messages[:-1]):
                    if isinstance(msg, HumanMessage):
                        prev_user_msg = msg.content
                        break
                
                if prev_user_msg:
                    combined_message = f"{prev_user_msg} {user_message}"
                    logger.info(f"이전 질문과 결합: {prev_user_msg[:50]}... + {user_message[:50]}...")
                    user_message_for_classification = combined_message
        else:
            if has_independent_keyword:
                logger.info(f"독립적인 질문 감지 (주제 키워드 포함) - 결합하지 않음: {user_message[:50]}...")
        
        return {
            "user_message_for_classification": user_message_for_classification,
            "has_independent_keyword": has_independent_keyword,
            "is_context_dependent": is_context_dependent,
            "has_context": has_context
        }
    
    @staticmethod
    def detect_transaction(user_message: str, user_message_for_classification: str) -> Optional[dict]:
        """규칙 1: 트랜잭션 해시 감지"""
        tx_hash = detect_transaction_hash(user_message_for_classification)
        if not tx_hash:
            return None
        
        # 출금/입금 관련 키워드가 함께 있으면 FAQ로 처리
        msg_lower = user_message_for_classification.lower()
        has_faq_keyword = any(keyword in msg_lower for keyword in config.TRANSACTION_FAQ_KEYWORDS)
        
        if has_faq_keyword:
            logger.info(f"트랜잭션 해시는 감지되었지만 출금/입금 관련 질문으로 판단 - FAQ로 분류")
            return None
        
        logger.info(f"트랜잭션 해시 감지: {tx_hash[:20]}...")
        routing_decision = RoutingDecision(
            question_type=QuestionType.TRANSACTION,
            confidence=0.95,
            reasoning=f"트랜잭션 해시가 감지되었습니다: {tx_hash[:20]}...",
            needs_faq_search=False,
            needs_web_search=False,
            needs_transaction_lookup=True,
            suggested_specialist="transaction"
        )
        print(f"[Router] ✅ 트랜잭션 질문으로 분류 (신뢰도: 0.95)", file=sys.stdout, flush=True)
        logger.info(f"✅ 트랜잭션 질문으로 분류")
        
        return {
            "routing_decision": routing_decision,
            "question_type": QuestionType.TRANSACTION,
            "transaction_hash": tx_hash,
            "specialist_used": "transaction"
        }
    
    @staticmethod
    def detect_price_query(user_message: str, user_message_for_classification: str, has_independent_keyword: bool) -> Optional[dict]:
        """규칙 2: 시세/가격 질문 감지"""
        # 독립적인 질문 키워드가 있으면 원본 메시지에서만 확인
        if has_independent_keyword:
            msg_lower = user_message.lower()
        else:
            msg_lower = user_message_for_classification.lower()
        
        has_price_query = any(keyword in msg_lower for keyword in config.PRICE_KEYWORDS)
        if not has_price_query:
            return None
        
        logger.info("시세/가격 질문 감지: web_search로 분류")
        routing_decision = RoutingDecision(
            question_type=QuestionType.WEB_SEARCH,
            confidence=0.95,
            reasoning=f"시세/가격 관련 질문으로 감지되었습니다. 실시간 정보가 필요하므로 web_search로 분류합니다.",
            needs_faq_search=False,
            needs_web_search=True,
            needs_transaction_lookup=False,
            suggested_specialist="web_search"
        )
        print(f"[Router] ✅ 시세/가격 질문으로 분류 (신뢰도: 0.95) - web_search", file=sys.stdout, flush=True)
        logger.info(f"✅ 시세/가격 질문으로 분류 - web_search")
        
        return {
            "routing_decision": routing_decision,
            "question_type": QuestionType.WEB_SEARCH,
            "needs_web_search": True,
            "specialist_used": "web_search"
        }
    
    @staticmethod
    def detect_date_time_query(user_message_for_classification: str) -> Optional[dict]:
        """규칙 2.5: 날짜/시간 질문 감지 (이벤트보다 우선)"""
        msg_lower = user_message_for_classification.lower()
        has_date_time_keyword = any(keyword in msg_lower for keyword in config.DATE_TIME_KEYWORDS)
        
        if not has_date_time_keyword:
            return None
        
        # 날짜/시간 질문은 FAQ Specialist로 (날짜/시간 직접 답변 로직이 있음)
        logger.info("날짜/시간 질문 감지: faq로 분류 (날짜/시간 직접 답변)")
        routing_decision = RoutingDecision(
            question_type=QuestionType.FAQ,
            confidence=0.95,
            reasoning=f"날짜/시간 관련 질문으로 감지되었습니다. FAQ Specialist에서 직접 답변합니다.",
            needs_faq_search=False,
            needs_web_search=False,
            needs_transaction_lookup=False,
            suggested_specialist="faq"
        )
        print(f"[Router] ✅ 날짜/시간 질문으로 분류 (신뢰도: 0.95) - faq", file=sys.stdout, flush=True)
        logger.info(f"✅ 날짜/시간 질문으로 분류 - faq")
        
        return {
            "routing_decision": routing_decision,
            "question_type": QuestionType.FAQ,
            "needs_web_search": False,
            "faq_threshold": 0.75,
            "specialist_used": "faq"
        }
    
    @staticmethod
    def detect_event_query(user_message_for_classification: str) -> Optional[dict]:
        """규칙 3: 이벤트/프로모션/공지사항 감지"""
        msg_lower = user_message_for_classification.lower()
        has_event_keyword = any(keyword in msg_lower for keyword in config.EVENT_KEYWORDS)
        
        if not has_event_keyword:
            return None
        
        logger.info("이벤트/프로모션/공지사항 질문 감지: web_search로 분류")
        routing_decision = RoutingDecision(
            question_type=QuestionType.WEB_SEARCH,
            confidence=0.95,
            reasoning=f"이벤트/프로모션/공지사항 관련 질문으로 감지되었습니다. 최신 정보가 필요하므로 web_search로 분류합니다.",
            needs_faq_search=False,
            needs_web_search=True,
            needs_transaction_lookup=False,
            suggested_specialist="web_search"
        )
        print(f"[Router] ✅ 이벤트/공지사항 질문으로 분류 (신뢰도: 0.95) - web_search", file=sys.stdout, flush=True)
        logger.info(f"✅ 이벤트/공지사항 질문으로 분류 - web_search")
        
        return {
            "routing_decision": routing_decision,
            "question_type": QuestionType.WEB_SEARCH,
            "needs_web_search": True,
            "specialist_used": "web_search"
        }
    
    @staticmethod
    def detect_faq_query(user_message_for_classification: str, has_independent_keyword: bool, has_price_query: bool, has_event_keyword: bool) -> Optional[dict]:
        """규칙 4: FAQ 질문 감지"""
        # 독립적인 질문 키워드가 있고, 시세/이벤트 키워드가 없으면 FAQ로 분류
        if not has_independent_keyword or has_price_query or has_event_keyword:
            return None
        
        msg_lower = user_message_for_classification.lower()
        has_faq_keyword = any(keyword in msg_lower for keyword in config.FAQ_KEYWORDS)
        
        if not has_faq_keyword:
            return None
        
        logger.info("FAQ 질문 감지: faq로 분류")
        routing_decision = RoutingDecision(
            question_type=QuestionType.FAQ,
            confidence=0.9,
            reasoning=f"FAQ 관련 질문으로 감지되었습니다. (키워드: {[k for k in config.FAQ_KEYWORDS if k in msg_lower][:3]})",
            needs_faq_search=True,
            needs_web_search=False,
            needs_transaction_lookup=False,
            suggested_specialist="faq"
        )
        print(f"[Router] ✅ FAQ 질문으로 분류 (신뢰도: 0.9) - faq", file=sys.stdout, flush=True)
        logger.info(f"✅ FAQ 질문으로 분류 - faq")
        
        return {
            "routing_decision": routing_decision,
            "question_type": QuestionType.FAQ,
            "needs_web_search": False,
            "faq_threshold": 0.75,
            "specialist_used": "faq"
        }
    
    @staticmethod
    def detect_simple_chat(user_message: str, user_message_for_classification: str, is_context_dependent: bool, has_context: bool) -> Optional[dict]:
        """규칙 1.5: 단순 대화 감지 (트랜잭션 다음, 다른 규칙보다 우선)"""
        # 맥락 의존적 질문은 단순 대화가 아님
        if is_context_dependent and has_context:
            return None
        
        # 원본 메시지와 분류용 메시지 모두 확인
        msg_lower_original = user_message.lower().strip()
        msg_lower_for_simple = user_message_for_classification.lower().strip()
        
        simple_chat_keywords_lower = [kw.lower() for kw in config.SIMPLE_CHAT_KEYWORDS]
        
        # 정확한 키워드 매칭 확인
        is_exact_match = False
        matched_keyword = None
        
        for keyword in simple_chat_keywords_lower:
            if (msg_lower_original == keyword or 
                msg_lower_original.startswith(keyword + ' ') or 
                msg_lower_original.endswith(' ' + keyword) or
                msg_lower_original == keyword):
                is_exact_match = True
                matched_keyword = keyword
                break
        
        # 정확한 매칭이 아니면, 짧은 메시지에서 키워드 포함 여부 확인
        if not is_exact_match:
            has_simple_keyword = any(keyword in msg_lower_for_simple for keyword in simple_chat_keywords_lower)
            is_short = len(user_message_for_classification.strip()) <= config.SIMPLE_CHAT_MAX_LENGTH
            
            if not (has_simple_keyword and is_short):
                return None
        else:
            is_short = True
        
        # 날짜/시간 질문 키워드가 포함되어 있으면 제외
        has_date_time_query = any(keyword in msg_lower_for_simple for keyword in config.DATE_TIME_KEYWORDS)
        if has_date_time_query and not is_exact_match:
            return None
        
        logger.info(f"단순 대화로 분류 (매칭 키워드: {matched_keyword or '키워드 포함'})")
        routing_decision = RoutingDecision(
            question_type=QuestionType.SIMPLE_CHAT,
            confidence=0.95 if is_exact_match else 0.9,
            reasoning=f"단순 인사나 감사 표현으로 판단됩니다. (키워드: {matched_keyword or '키워드 포함'})",
            needs_faq_search=False,
            needs_web_search=False,
            needs_transaction_lookup=False,
            suggested_specialist="simple_chat"
        )
        print(f"[Router] ✅ 단순 대화로 분류 (신뢰도: {routing_decision.confidence:.2f})", file=sys.stdout, flush=True)
        logger.info(f"✅ 단순 대화로 분류")
        
        return {
            "routing_decision": routing_decision,
            "question_type": QuestionType.SIMPLE_CHAT,
            "specialist_used": "simple_chat"
        }
    
    @classmethod
    def classify(cls, state: ChatState, user_message: str) -> tuple[Optional[dict], dict]:
        """규칙 기반 분류 체인 실행 (우선순위 순)
        
        Returns:
            tuple: (분류 결과 dict 또는 None, 맥락 정보 dict)
        """
        # 맥락 분석
        context_info = cls.analyze_context(state, user_message)
        user_message_for_classification = context_info["user_message_for_classification"]
        has_independent_keyword = context_info["has_independent_keyword"]
        is_context_dependent = context_info["is_context_dependent"]
        has_context = context_info["has_context"]
        
        # 가격/이벤트 키워드 사전 계산
        msg_lower_for_price = (user_message_for_classification if not has_independent_keyword else user_message).lower()
        has_price_query = any(keyword in msg_lower_for_price for keyword in config.PRICE_KEYWORDS)
        has_event_keyword = any(keyword in user_message_for_classification.lower() for keyword in config.EVENT_KEYWORDS)
        
        # 규칙 체인 실행 (우선순위 순)
        rules = [
            lambda: cls.detect_transaction(user_message, user_message_for_classification),
            lambda: cls.detect_simple_chat(user_message, user_message_for_classification, is_context_dependent, has_context),
            lambda: cls.detect_price_query(user_message, user_message_for_classification, has_independent_keyword),
            lambda: cls.detect_date_time_query(user_message_for_classification),
            lambda: cls.detect_event_query(user_message_for_classification),
            lambda: cls.detect_faq_query(
                user_message_for_classification, 
                has_independent_keyword,
                has_price_query,
                has_event_keyword
            )
        ]
        
        for rule_func in rules:
            result = rule_func()
            if result:
                logger.info("="*60)
                print("="*60, file=sys.stdout, flush=True)
                return result, context_info
        
        # 모든 규칙이 매칭되지 않음
        return None, context_info


def _get_router_llm():
    """Router LLM 인스턴스 생성"""
    import os
    router_model = os.getenv("ROUTER_MODEL") or os.getenv("OPENAI_MODEL") or config._DEFAULT_MODEL
    return ChatOpenAI(
        model=router_model,
        temperature=0.1,
        openai_api_key=config.OPENAI_API_KEY
    )


@traceable(name="router", run_type="llm")
async def router(state: ChatState):
    """Router: 질문 분류 및 라우팅 결정"""
    print("="*60, file=sys.stdout, flush=True)
    print("Router 노드 시작: 질문 분류 및 라우팅", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    ensure_logger_setup()
    logger.info("="*60)
    logger.info("Router 노드 시작: 질문 분류 및 라우팅")
    
    user_message = extract_user_message(state)
    if not user_message:
        logger.warning("Router: 사용자 메시지 없음")
        return {
            "routing_decision": None,
            "question_type": QuestionType.GENERAL,
            "specialist_used": "faq"
        }
    
    logger.info(f"사용자 질문: {user_message[:100]}...")
    
    # 규칙 기반 분류 시도
    rule_result, context_info = RuleBasedClassifier.classify(state, user_message)
    if rule_result:
        return rule_result
    
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
        router_llm = _get_router_llm()
        routing_decision = await router_llm.with_structured_output(RoutingDecision).ainvoke(
            [HumanMessage(content=routing_prompt)]
        )
        
        print(f"[Router] ✅ 질문 분류 완료: {routing_decision.question_type.value} (신뢰도: {routing_decision.confidence:.2f})", file=sys.stdout, flush=True)
        logger.info(f"✅ 질문 분류 완료: {routing_decision.question_type.value}")
        
        # 모호한 질문 감지
        is_ambiguous = (
            routing_decision.confidence < 0.6 or
            routing_decision.needs_clarification or
            routing_decision.question_type == QuestionType.GENERAL
        )
        
        if is_ambiguous:
            logger.info("⚠️ 모호한 질문 감지 - Intent Clarifier로 라우팅")
            return {
                "routing_decision": routing_decision,
                "question_type": QuestionType.INTENT_CLARIFICATION,
                "needs_clarification": True,
                "specialist_used": "intent_clarifier"
            }
        
        logger.info("="*60)
        print("="*60, file=sys.stdout, flush=True)
        
        result_state = {
            "routing_decision": routing_decision,
            "question_type": routing_decision.question_type,
            "needs_web_search": routing_decision.needs_web_search,
            "faq_threshold": 0.75 if routing_decision.question_type == QuestionType.FAQ else 0.7,
            "specialist_used": routing_decision.suggested_specialist,
            "needs_clarification": False
        }
        
        # 트랜잭션 타입인 경우 해시 설정
        if routing_decision.question_type == QuestionType.TRANSACTION:
            detected_hash = detect_transaction_hash(user_message)
            if detected_hash:
                result_state["transaction_hash"] = detected_hash
                logger.info(f"✅ 트랜잭션 해시 감지: {detected_hash[:20]}...")
        
        return result_state
    except Exception as e:
        error_result = handle_node_error(e, "router", state, log_level="error")
        return {
            **error_result,
            "routing_decision": None,
            "question_type": QuestionType.GENERAL,
            "specialist_used": "faq",
            "faq_threshold": 0.7,
            "needs_clarification": False
        }

