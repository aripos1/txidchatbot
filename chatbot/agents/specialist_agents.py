"""
Specialist 에이전트들 - FAQ, Transaction, SimpleChat 에이전트
기존 노드 함수들을 에이전트로 래핑하여 멀티 에이전트 구조로 변환
"""
import sys
import logging
from typing import List
from langchain_core.messages import AIMessage

from .base_agent import BaseAgent
from ..models import ChatState, QuestionType
from ..nodes.specialists import (
    faq_specialist as faq_specialist_func,
    transaction_specialist as transaction_specialist_func,
    simple_chat_specialist as simple_chat_specialist_func,
)

logger = logging.getLogger(__name__)


class FAQAgent(BaseAgent):
    """FAQ Specialist 에이전트 - FAQ 벡터 DB 검색 및 답변"""
    
    def __init__(self):
        super().__init__(
            name="FAQAgent",
            description="FAQ 벡터 DB 검색 및 빗썸 고객지원 페이지 검색을 수행하는 전문가 에이전트"
        )
        self.update_state(
            search_count=0,
            success_count=0,
            avg_score=0.0
        )
    
    async def process(self, state: ChatState) -> ChatState:
        """FAQ 처리 로직"""
        self.update_state(search_count=self.get_state("search_count", 0) + 1)
        
        # 기존 FAQ Specialist 함수 호출
        result = await faq_specialist_func(state)
        
        # 에이전트 메모리에 결과 저장
        db_results = result.get("db_search_results", [])
        if db_results:
            best_score = db_results[0].get("score", 0) if db_results else 0
            self.add_to_memory("last_search_score", best_score)
            self.add_to_memory("last_search_results_count", len(db_results))
            
            # 성공률 업데이트
            success_count = self.get_state("success_count", 0)
            if best_score > 0.7:
                success_count += 1
            self.update_state(success_count=success_count)
        
        updated_state = {**state, **result}
        
        # Hybrid 필요 여부 확인 - 멀티 에이전트 협업
        needs_web_search = result.get("needs_web_search", False)
        best_score = result.get("best_score", 0.0)
        
        if needs_web_search:
            logger.info(f"📞 [{self.name}] FAQ 결과 부족 (점수: {best_score:.2f}) - PlannerAgent 호출")
            print(f"📞 [{self.name}] FAQ 결과 부족 - 웹 검색 시작", file=sys.stdout, flush=True)
            # PlannerAgent를 직접 호출 (멀티 에이전트 협업)
            try:
                updated_state = await self.call_agent("PlannerAgent", updated_state)
            except Exception as e:
                logger.error(f"⚠️ [{self.name}] PlannerAgent 호출 실패: {e}")
        else:
            # 결과 충분 → save_response 호출 (정해진 다음 단계)
            logger.info(f"✅ [{self.name}] FAQ 결과 충분 (점수: {best_score:.2f}) - save_response 호출")
            print(f"✅ [{self.name}] FAQ 결과 충분 - 응답 저장", file=sys.stdout, flush=True)
            from ..nodes.save_response import save_response as save_response_func
            updated_state = await save_response_func(updated_state)
        
        return updated_state
    
    def can_handle(self, state: ChatState) -> bool:
        """FAQ 질문인지 확인"""
        question_type = state.get("question_type")
        specialist_used = state.get("specialist_used")
        return (
            question_type == QuestionType.FAQ or
            specialist_used == "faq" or
            question_type == QuestionType.GENERAL
        )
    
    def is_task_complete(self, state: ChatState) -> bool:
        """FAQ 작업 완료 여부 자율 판단"""
        # needs_web_search가 설정되어 있으면 추가 작업 필요
        if state.get("needs_web_search", False):
            return False
        
        # DB 검색 결과가 있고 점수가 높으면 완료
        db_results = state.get("db_search_results", [])
        if db_results and len(db_results) > 0:
            best_score = db_results[0].get("score", 0)
            if best_score >= 0.7:
                return True
        
        # 메시지가 추가되었으면 완료
        return super().is_task_complete(state)
    
    def get_capabilities(self) -> List[str]:
        return [
            "FAQ 벡터 DB 검색",
            "빗썸 고객지원 페이지 검색",
            "날짜/시간 직접 답변",
            "Hybrid 모드 위임"
        ]


class TransactionAgent(BaseAgent):
    """Transaction Specialist 에이전트 - 트랜잭션 조회"""
    
    def __init__(self):
        super().__init__(
            name="TransactionAgent",
            description="멀티체인 트랜잭션 해시 조회를 수행하는 전문가 에이전트"
        )
        self.update_state(
            lookup_count=0,
            success_count=0,
            chains_queried=set()
        )
    
    async def process(self, state: ChatState) -> ChatState:
        """트랜잭션 처리 로직"""
        self.update_state(lookup_count=self.get_state("lookup_count", 0) + 1)
        
        # 기존 Transaction Specialist 함수 호출
        result = await transaction_specialist_func(state)
        
        # 에이전트 메모리에 결과 저장
        tx_results = result.get("transaction_results")
        if tx_results:
            if isinstance(tx_results, list):
                chains = [r.get("chain") for r in tx_results if r.get("chain")]
                self.add_to_memory("last_lookup_chains", chains)
                self.add_to_memory("last_lookup_count", len(tx_results))
                
                # 체인별 통계 업데이트
                chains_queried = self.get_state("chains_queried", set())
                chains_queried.update(chains)
                self.update_state(chains_queried=chains_queried)
                
                # 성공률 업데이트
                success_count = self.get_state("success_count", 0)
                if len(tx_results) > 0:
                    success_count += 1
                self.update_state(success_count=success_count)
        
        # 멀티 에이전트: save_response 호출 (정해진 다음 단계)
        updated_state = {**state, **result}
        logger.info(f"✅ [{self.name}] 트랜잭션 조회 완료 - save_response 호출")
        print(f"✅ [{self.name}] 트랜잭션 조회 완료 - 응답 저장", file=sys.stdout, flush=True)
        from ..nodes.save_response import save_response as save_response_func
        updated_state = await save_response_func(updated_state)
        
        return updated_state
    
    def can_handle(self, state: ChatState) -> bool:
        """트랜잭션 질문인지 확인"""
        question_type = state.get("question_type")
        specialist_used = state.get("specialist_used")
        transaction_hash = state.get("transaction_hash")
        return (
            question_type == QuestionType.TRANSACTION or
            specialist_used == "transaction" or
            transaction_hash is not None
        )
    
    def is_task_complete(self, state: ChatState) -> bool:
        """Transaction 작업 완료 여부 자율 판단"""
        # 트랜잭션 결과가 있으면 완료
        tx_results = state.get("transaction_results")
        if tx_results:
            return True
        
        # 메시지가 추가되었으면 완료
        return super().is_task_complete(state)
    
    def get_capabilities(self) -> List[str]:
        return [
            "트랜잭션 해시 감지",
            "31개 체인 멀티체인 조회",
            "트랜잭션 결과 포맷팅",
            "블록 탐색기 링크 생성"
        ]


class SimpleChatAgent(BaseAgent):
    """SimpleChat Specialist 에이전트 - 단순 대화 처리"""
    
    def __init__(self):
        super().__init__(
            name="SimpleChatAgent",
            description="단순 대화, 인사, 감사 표현을 처리하는 전문가 에이전트"
        )
        self.update_state(
            response_count=0,
            context_used_count=0
        )
    
    async def process(self, state: ChatState) -> ChatState:
        """단순 대화 처리 로직"""
        self.update_state(response_count=self.get_state("response_count", 0) + 1)
        
        # 기존 SimpleChat Specialist 함수 호출
        result = await simple_chat_specialist_func(state)
        
        # 맥락 사용 여부 확인
        messages = state.get("messages", [])
        if len(messages) > 1:
            self.update_state(context_used_count=self.get_state("context_used_count", 0) + 1)
            self.add_to_memory("last_context_used", True)
        else:
            self.add_to_memory("last_context_used", False)
        
        # 멀티 에이전트: save_response 호출 (정해진 다음 단계)
        updated_state = {**state, **result}
        logger.info(f"✅ [{self.name}] 단순 대화 처리 완료 - save_response 호출")
        print(f"✅ [{self.name}] 단순 대화 완료 - 응답 저장", file=sys.stdout, flush=True)
        from ..nodes.save_response import save_response as save_response_func
        updated_state = await save_response_func(updated_state)
        
        return updated_state
    
    def can_handle(self, state: ChatState) -> bool:
        """단순 대화 질문인지 확인"""
        question_type = state.get("question_type")
        specialist_used = state.get("specialist_used")
        return (
            question_type == QuestionType.SIMPLE_CHAT or
            specialist_used == "simple_chat"
        )
    
    def is_task_complete(self, state: ChatState) -> bool:
        """SimpleChat 작업 완료 여부 자율 판단"""
        # 단순 대화는 항상 한 번에 완료
        messages = state.get("messages", [])
        if messages:
            from langchain_core.messages import AIMessage
            # 마지막 메시지가 AI 응답이면 완료
            if messages[-1].__class__.__name__ == 'AIMessage':
                return True
        return False
    
    def get_capabilities(self) -> List[str]:
        return [
            "단순 대화 처리",
            "인사/감사 표현 응답",
            "대화 맥락 활용",
            "날짜/시간 정보 제공"
        ]


# 에이전트 인스턴스 생성 (싱글톤 패턴)
_faq_agent = None
_transaction_agent = None
_simple_chat_agent = None


def get_faq_agent() -> FAQAgent:
    """FAQ 에이전트 인스턴스 가져오기"""
    global _faq_agent
    if _faq_agent is None:
        _faq_agent = FAQAgent()
    return _faq_agent


def get_transaction_agent() -> TransactionAgent:
    """Transaction 에이전트 인스턴스 가져오기"""
    global _transaction_agent
    if _transaction_agent is None:
        _transaction_agent = TransactionAgent()
    return _transaction_agent


def get_simple_chat_agent() -> SimpleChatAgent:
    """SimpleChat 에이전트 인스턴스 가져오기"""
    global _simple_chat_agent
    if _simple_chat_agent is None:
        _simple_chat_agent = SimpleChatAgent()
    return _simple_chat_agent


# 기존 코드 호환성을 위한 래퍼 함수
async def faq_specialist(state: ChatState) -> ChatState:
    """기존 코드 호환성을 위한 래퍼"""
    agent = get_faq_agent()
    return await agent(state)


async def transaction_specialist(state: ChatState) -> ChatState:
    """기존 코드 호환성을 위한 래퍼"""
    agent = get_transaction_agent()
    return await agent(state)


async def simple_chat_specialist(state: ChatState) -> ChatState:
    """기존 코드 호환성을 위한 래퍼"""
    agent = get_simple_chat_agent()
    return await agent(state)
