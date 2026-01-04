"""
챗봇 그래프에서 사용하는 타입 정의
"""
from typing import TypedDict, Annotated, Sequence, Optional
from enum import Enum
import operator
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

# 질문 유형 Enum
class QuestionType(str, Enum):
    """질문 유형 분류"""
    SIMPLE_CHAT = "simple_chat"        # 단순 대화
    FAQ = "faq"                        # FAQ 질문
    TRANSACTION = "transaction"         # 트랜잭션 조회
    WEB_SEARCH = "web_search"          # 웹 검색 필요 (이벤트, 공지사항)
    HYBRID = "hybrid"                  # FAQ + 웹 검색 조합
    GENERAL = "general"                # 일반 문의 (기본 처리)
    INTENT_CLARIFICATION = "intent_clarification"  # 의도 명확화 필요

# 구조화된 출력 모델 (Open Deep Research 스타일)
class SearchPlan(BaseModel):
    """검색 계획 구조화된 출력"""
    search_queries: list[str] = Field(
        description="웹 검색을 위한 검색 쿼리 목록 (5-7개 권장)",
        min_length=1,
        max_length=7
    )
    research_plan: str = Field(
        description="연구 계획 설명"
    )
    priority: int = Field(
        description="검색 우선순위 (1-5, 높을수록 중요)",
        ge=1,
        le=5,
        default=3
    )

# Grader 평가 결과 구조화된 출력
class GraderResult(BaseModel):
    """Grader 평가 결과 구조화된 출력"""
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="검색 결과가 질문에 답하기에 충분한지 점수 (0.0-1.0)"
    )
    is_sufficient: bool = Field(
        description="검색 결과가 충분한지 여부 (True: 답변 가능, False: 재검색 필요)"
    )
    feedback: str = Field(
        description="평가 피드백 및 개선 제안"
    )
    missing_information: Optional[str] = Field(
        default=None,
        description="부족한 정보가 있다면 무엇인지"
    )

# 응답 검증 결과 구조화된 출력
class ValidationResult(BaseModel):
    """응답 검증 결과 구조화된 출력"""
    validation_score: float = Field(
        ge=0.0,
        le=1.0,
        description="응답 검증 점수 (0.0-1.0)"
    )
    is_valid: bool = Field(
        description="응답이 검증을 통과했는지 여부"
    )
    issues: list[str] = Field(
        default_factory=list,
        description="발견된 문제점 리스트"
    )
    suggested_fixes: list[str] = Field(
        default_factory=list,
        description="수정 제안 리스트"
    )

# 의도 명확화 결과 구조화된 출력
class IntentClarification(BaseModel):
    """의도 명확화 결과 구조화된 출력"""
    needs_clarification: bool = Field(
        description="명확화가 필요한지 여부"
    )
    possible_intents: list[str] = Field(
        default_factory=list,
        description="가능한 의도 목록"
    )
    clarification_question: str = Field(
        default="",
        description="사용자에게 물어볼 명확화 질문"
    )
    suggested_intent: Optional[str] = Field(
        default=None,
        description="가장 가능성 높은 의도 (명확화 불필요 시)"
    )

# 라우팅 결정 구조화된 출력
class RoutingDecision(BaseModel):
    """라우팅 결정 구조화된 출력"""
    question_type: QuestionType = Field(
        description="질문 유형"
    )
    confidence: float = Field(
        ge=0.0, 
        le=1.0, 
        description="분류 신뢰도"
    )
    reasoning: str = Field(
        description="라우팅 결정 이유"
    )
    needs_faq_search: bool = Field(
        description="FAQ 검색 필요 여부"
    )
    needs_web_search: bool = Field(
        description="웹 검색 필요 여부"
    )
    needs_transaction_lookup: bool = Field(
        description="트랜잭션 조회 필요 여부"
    )
    suggested_specialist: str = Field(
        description="권장 전문가"
    )
    needs_clarification: bool = Field(
        default=False,
        description="의도 명확화가 필요한지 여부"
    )

class ChatState(TypedDict, total=False):
    """챗봇 상태 정의 (Router-Specialist 아키텍처 확장 + 순환형 구조)
    
    total=False로 설정하여 모든 필드를 선택적으로 만듭니다.
    필수 필드는 messages와 session_id입니다.
    """
    # 필수 필드
    messages: Annotated[Sequence[BaseMessage], operator.add]
    session_id: str
    
    # Router 관련 (Optional)
    routing_decision: Optional[RoutingDecision]  # 라우팅 결정
    question_type: Optional[QuestionType]  # 질문 유형
    specialist_used: Optional[str]  # 사용된 전문가
    needs_clarification: bool  # 의도 명확화 필요 여부
    
    # FAQ 관련 (Optional)
    db_search_results: list  # 벡터 DB 검색 결과
    faq_threshold: float  # FAQ 전문가용 임계값
    
    # 웹 검색 관련 (순환형 구조, Optional)
    needs_deep_research: bool  # Deep Research 필요 여부
    research_plan: str  # 연구 계획
    search_queries: list  # 웹 검색 쿼리 목록
    web_search_results: list  # 웹 검색 결과
    search_loop_count: int  # 검색 반복 횟수 (순환형 구조)
    grader_score: Optional[float]  # Grader 평가 점수
    grader_feedback: Optional[str]  # Grader 피드백
    is_sufficient: Optional[bool]  # 검색 결과 충분 여부 (Grader 결과)
    
    # 요약/압축 (선택적 사용)
    summarized_results: list  # 요약된 검색 결과 (선택적)
    compressed_results: list  # 압축된 검색 결과 (선택적)
    
    # 트랜잭션 관련 (Optional)
    transaction_hash: Optional[str]  # 트랜잭션 해시
    transaction_results: Optional[dict]  # 트랜잭션 조회 결과
    
    # 응답 검증 관련 (Optional)
    validation_score: Optional[float]  # 응답 검증 점수
    validation_issues: Optional[list]  # 검증에서 발견된 문제점
    suggested_fixes: Optional[list]  # 수정 제안
    is_valid: Optional[bool]  # 검증 통과 여부
    refinement_count: int  # 응답 개선 반복 횟수


def get_default_chat_state(
    session_id: str,
    messages: Optional[Sequence[BaseMessage]] = None
) -> ChatState:
    """ChatState의 기본값을 가진 상태 딕셔너리를 생성합니다.
    
    Args:
        session_id: 세션 ID (필수)
        messages: 초기 메시지 목록 (선택적, 없으면 빈 리스트)
    
    Returns:
        기본값이 설정된 ChatState 딕셔너리
    
    Example:
        >>> state = get_default_chat_state("session-123", [HumanMessage(content="안녕")])
        >>> state["session_id"]
        'session-123'
        >>> state["needs_clarification"]
        False
        >>> state["search_loop_count"]
        0
    """
    return {
        # 필수 필드
        "messages": messages if messages is not None else [],
        "session_id": session_id,
        
        # Router 관련 기본값
        "routing_decision": None,
        "question_type": None,
        "specialist_used": None,
        "needs_clarification": False,
        
        # FAQ 관련 기본값
        "db_search_results": [],
        "faq_threshold": 0.7,  # 기본 임계값 0.7
        
        # 웹 검색 관련 기본값
        "needs_deep_research": False,
        "research_plan": "",
        "search_queries": [],
        "web_search_results": [],
        "search_loop_count": 0,
        "grader_score": None,
        "grader_feedback": None,
        "is_sufficient": None,
        
        # 요약/압축 기본값
        "summarized_results": [],
        "compressed_results": [],
        
        # 트랜잭션 관련 기본값
        "transaction_hash": None,
        "transaction_results": None,
        
        # 응답 검증 관련 기본값
        "validation_score": None,
        "validation_issues": None,
        "suggested_fixes": None,
        "is_valid": None,
        "refinement_count": 0,
    }

