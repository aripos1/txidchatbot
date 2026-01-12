"""
챗봇 그래프에서 사용하는 헬퍼 함수들
"""
import logging
import sys
import re
from typing import Optional, Dict, Any
from .models import ChatState
from langchain_core.messages import HumanMessage, AIMessage

# 로거 설정
logger = logging.getLogger(__name__)

def ensure_logger_setup():
    """로거가 제대로 설정되었는지 확인하고 필요시 재설정"""
    root = logging.getLogger()
    # 루트 로거로 전파
    logger.propagate = True
    # 핸들러 제거 (루트 로거의 핸들러 사용)
    logger.handlers.clear()
    # 루트 로거에 핸들러가 없으면 추가
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)
        root.setLevel(logging.INFO)

def extract_user_message(state: ChatState) -> str:
    """상태에서 사용자 메시지 추출"""
    messages = state.get("messages", [])
    user_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
    return user_messages[-1].content if user_messages else ""

def extract_conversation_context(state: ChatState, limit: int = 5) -> str:
    """상태에서 최근 대화 맥락 추출"""
    messages = state.get("messages", [])
    if not messages:
        return ""
    
    # 최근 대화만 추출 (사용자와 AI 메시지 모두)
    recent_messages = messages[-limit*2:] if len(messages) > limit*2 else messages
    
    context_parts = []
    for msg in recent_messages:
        if isinstance(msg, HumanMessage):
            context_parts.append(f"사용자: {msg.content}")
        elif isinstance(msg, AIMessage):
            context_parts.append(f"챗봇: {msg.content}")
    
    return "\n".join(context_parts)

def detect_transaction_hash(text: str) -> Optional[str]:
    """텍스트에서 트랜잭션 해시 감지"""
    if not text:
        return None
    
    # 공백 제거 및 소문자 변환 (매칭을 위해)
    text_clean = text.strip()
    
    # 0x 접두사가 있는 66자 hex 패턴 (0x + 64자)
    # \b 경계를 제거하고 더 유연한 패턴 사용
    hex_with_prefix_pattern = r'0x[0-9a-fA-F]{64}'
    # 0x 접두사가 없는 64자 hex 패턴
    hex_pattern = r'[0-9a-fA-F]{64}'
    # Base64 패턴 (44-48자)
    base64_pattern = r'[A-Za-z0-9+/]{44,48}={0,2}'
    # Base58 패턴 (Solana 등, 32-88자) - Base58은 1, I, O, 0을 제외한 영숫자
    base58_pattern = r'[1-9A-HJ-NP-Za-km-z]{32,88}'
    
    # 0x 접두사가 있는 경우 우선 처리
    hex_with_prefix_match = re.search(hex_with_prefix_pattern, text_clean, re.IGNORECASE)
    if hex_with_prefix_match:
        matched = hex_with_prefix_match.group(0)
        logger.debug(f"해시 감지 (0x 접두사): {matched[:20]}...")
        return matched
    
    # 0x 접두사가 없는 64자 hex 패턴
    # 단, 0x로 시작하지 않는 경우에만 매칭 (이미 0x 패턴을 확인했으므로)
    hex_match = re.search(hex_pattern, text_clean, re.IGNORECASE)
    if hex_match:
        matched = hex_match.group(0)
        # 0x로 시작하는 더 긴 패턴이 아닌지 확인
        if not text_clean[max(0, hex_match.start()-2):hex_match.start()].lower().endswith('0x'):
            logger.debug(f"해시 감지 (64자 hex): {matched[:20]}...")
            return matched
    
    # Base58 패턴 (Solana 등) - Base64보다 먼저 체크 (더 긴 패턴이므로)
    # Base58은 Base64와 겹칠 수 있으므로, 더 긴 패턴을 우선 매칭
    base58_match = re.search(base58_pattern, text_clean)
    if base58_match:
        matched = base58_match.group(0)
        logger.debug(f"해시 감지 (Base58, {len(matched)}자): {matched[:20]}...")
        return matched
    
    # Base64 패턴 (44-48자)
    base64_match = re.search(base64_pattern, text_clean)
    if base64_match:
        matched = base64_match.group(0)
        logger.debug(f"해시 감지 (Base64, {len(matched)}자): {matched[:20]}...")
        return matched
    
    logger.debug(f"해시 감지 실패. 텍스트 길이: {len(text_clean)}, 처음 100자: {text_clean[:100]}")
    return None


# ========== 에러 핸들링 유틸리티 ==========

class ChatbotError(Exception):
    """챗봇 관련 커스텀 에러"""
    def __init__(self, message: str, node_name: str = "unknown", original_error: Optional[Exception] = None):
        self.message = message
        self.node_name = node_name
        self.original_error = original_error
        super().__init__(self.message)


def handle_node_error(
    error: Exception,
    node_name: str,
    state: Optional[ChatState] = None,
    fallback_message: Optional[str] = None,
    log_level: str = "error"
) -> Dict[str, Any]:
    """노드에서 발생한 에러를 통일된 방식으로 처리합니다.
    
    Args:
        error: 발생한 예외
        node_name: 에러가 발생한 노드 이름
        state: 현재 상태 (선택적)
        fallback_message: 사용자에게 보여줄 대체 메시지 (선택적)
        log_level: 로그 레벨 ("error", "warning", "info")
    
    Returns:
        상태 업데이트 딕셔너리 (messages 포함)
    
    Example:
        >>> try:
        ...     result = await some_operation()
        ... except Exception as e:
        ...     return handle_node_error(e, "router", state)
    """
    # 로그 메시지 포맷팅
    error_type = type(error).__name__
    error_message = str(error)
    user_message = extract_user_message(state) if state else "N/A"
    
    log_message = (
        f"❌ [{node_name}] 에러 발생: {error_type} - {error_message}\n"
        f"   사용자 메시지: {user_message[:100]}..."
    )
    
    # 로그 레벨에 따라 기록
    if log_level == "error":
        logger.error(log_message, exc_info=True)
        print(f"[{node_name}] ❌ 에러: {error_type}", file=sys.stdout, flush=True)
    elif log_level == "warning":
        logger.warning(log_message)
        print(f"[{node_name}] ⚠️ 경고: {error_type}", file=sys.stdout, flush=True)
    else:
        logger.info(log_message)
    
    # 기본 Fallback 메시지
    if fallback_message is None:
        fallback_message = get_default_error_message(node_name)
    
    # 상태 업데이트 반환
    return {
        "messages": [AIMessage(content=fallback_message)]
    }


def get_default_error_message(node_name: str) -> str:
    """노드별 기본 에러 메시지를 반환합니다.
    
    Args:
        node_name: 노드 이름
    
    Returns:
        사용자에게 보여줄 에러 메시지
    """
    error_messages = {
        "router": "죄송합니다. 질문을 분류하는 중 오류가 발생했습니다. 다시 시도해주세요.",
        "simple_chat_specialist": "안녕하세요! 무엇을 도와드릴까요?",
        "intent_clarifier": "죄송합니다. 질문을 이해하는 중 오류가 발생했습니다. 다시 말씀해주시겠어요?",
        "faq_specialist": "죄송합니다. FAQ 검색 중 오류가 발생했습니다. 다시 시도해주세요.",
        "transaction_specialist": "죄송합니다. 트랜잭션 조회 중 오류가 발생했습니다. 다시 시도해주세요.",
        "planner": "죄송합니다. 검색 계획을 수립하는 중 오류가 발생했습니다. 다시 시도해주세요.",
        "researcher": "죄송합니다. 정보 검색 중 오류가 발생했습니다. 다시 시도해주세요.",
        "grader": "죄송합니다. 검색 결과 평가 중 오류가 발생했습니다. 다시 시도해주세요.",
        "writer": "죄송합니다. 답변 생성 중 오류가 발생했습니다. 다시 시도해주세요.",
        "summarizer": "죄송합니다. 정보 요약 중 오류가 발생했습니다. 다시 시도해주세요.",
        "check_db": "죄송합니다. 데이터베이스 검색 중 오류가 발생했습니다. 다시 시도해주세요.",
        "save_response": "죄송합니다. 응답 저장 중 오류가 발생했습니다. 답변은 정상적으로 생성되었습니다.",
    }
    
    return error_messages.get(
        node_name,
        "죄송합니다. 처리 중 오류가 발생했습니다. 다시 시도해주세요."
    )


def get_fallback_message() -> str:
    """일반적인 Fallback 메시지를 반환합니다.
    
    Returns:
        Fallback 메시지
    """
    return (
        "죄송합니다. 현재 신뢰할 수 있는 정보를 찾을 수 없습니다.\n\n"
        "빗썸 공식 홈페이지: https://www.bithumb.com 또는 앱에서 직접 확인하시기 바랍니다.\n\n"
        "더 자세한 정보는 빗썸 고객지원 페이지: https://support.bithumb.com/hc/ko 에서 확인하실 수 있습니다."
    )


def create_error_state(
    error: Exception,
    node_name: str,
    state: Optional[ChatState] = None,
    custom_message: Optional[str] = None
) -> Dict[str, Any]:
    """에러 발생 시 상태를 생성합니다.
    
    Args:
        error: 발생한 예외
        node_name: 에러가 발생한 노드 이름
        state: 현재 상태 (선택적)
        custom_message: 커스텀 에러 메시지 (선택적)
    
    Returns:
        상태 업데이트 딕셔너리
    """
    return handle_node_error(
        error=error,
        node_name=node_name,
        state=state,
        fallback_message=custom_message
    )

