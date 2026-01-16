"""
챗봇 설정 관리 (Open Deep Research 스타일)
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)
# 루트 로거로 전파되도록 설정
logger.propagate = True
logger.handlers.clear()


class ChatbotConfiguration:
    """챗봇 설정 클래스"""
    
    # ========== LLM 설정 ==========
    # 기본 모델명
    _DEFAULT_MODEL: str = "gpt-4o-mini"
    
    # Planner LLM 설정
    PLANNER_MODEL: str = os.getenv("PLANNER_MODEL") or os.getenv("OPENAI_MODEL", _DEFAULT_MODEL)
    PLANNER_TEMPERATURE: float = float(os.getenv("PLANNER_TEMPERATURE", "0.1"))
    
    # Writer LLM 설정
    WRITER_MODEL: str = os.getenv("WRITER_MODEL") or os.getenv("OPENAI_MODEL", _DEFAULT_MODEL)
    WRITER_TEMPERATURE: float = float(os.getenv("WRITER_TEMPERATURE", "0.7"))
    
    # Summarization LLM 설정 (검색 결과 요약용)
    SUMMARIZATION_MODEL: str = os.getenv("SUMMARIZATION_MODEL") or os.getenv("OPENAI_MODEL", _DEFAULT_MODEL)
    SUMMARIZATION_TEMPERATURE: float = float(os.getenv("SUMMARIZATION_TEMPERATURE", "0.3"))
    
    # Compression LLM 설정 (연구 결과 압축용 - Open Deep Research 스타일)
    COMPRESSION_MODEL: str = os.getenv("COMPRESSION_MODEL") or os.getenv("OPENAI_MODEL", _DEFAULT_MODEL)
    COMPRESSION_TEMPERATURE: float = float(os.getenv("COMPRESSION_TEMPERATURE", "0.2"))
    
    # OpenAI API Key
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    
    # ========== 검색 설정 ==========
    # 검색 API 선택 (google, duckduckgo)
    SEARCH_API: str = os.getenv("SEARCH_API", "google")
    
    # 검색 결과 제한
    MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "20"))
    MAX_SEARCH_QUERIES: int = int(os.getenv("MAX_SEARCH_QUERIES", "7"))
    MAX_RESULTS_PER_QUERY: int = int(os.getenv("MAX_RESULTS_PER_QUERY", "8"))
    
    # Google Custom Search API
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    GOOGLE_CX: Optional[str] = os.getenv("GOOGLE_CX")
    
    # Tavily Search API
    TAVILY_API_KEY: Optional[str] = os.getenv("TAVILY_API_KEY")
    
    # CoinMarketCap API (시세 조회용)
    COINMARKETCAP_API_KEY: Optional[str] = os.getenv("COINMARKETCAP_API_KEY")
    
    # ========== 벡터 DB 설정 ==========
    # MongoDB 설정
    MONGODB_URI: Optional[str] = os.getenv("MONGODB_URI")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "chatbot_db")

    # ========== 하이브리드 검색 설정 (추가) ==========
    # 키워드 검색(BM25/Lexical) 가중치 (0.0 ~ 1.0)
    HYBRID_K_WEIGHT: float = float(os.getenv("HYBRID_K_WEIGHT", "0.7"))
    # 시맨틱 검색(Vector) 가중치 (0.0 ~ 1.0)
    HYBRID_S_WEIGHT: float = float(os.getenv("HYBRID_S_WEIGHT", "0.3"))
    # 최종적으로 Writer에게 보낼 최상위 결과 개수
    FINAL_TOP_K: int = int(os.getenv("FINAL_TOP_K", "5"))
    
    # 벡터 검색 설정
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
    VECTOR_SEARCH_LIMIT: int = int(os.getenv("VECTOR_SEARCH_LIMIT", "3"))
    
    # 임베딩 모델
    EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    
    # ========== 검색 결과 처리 설정 ==========
    # 요약 활성화 여부
    ENABLE_SUMMARIZATION: bool = os.getenv("ENABLE_SUMMARIZATION", "true").lower() == "true"
    
    # 요약 트리거 (검색 결과 개수)
    SUMMARIZATION_THRESHOLD: int = int(os.getenv("SUMMARIZATION_THRESHOLD", "10"))
    
    # 압축 활성화 여부
    ENABLE_COMPRESSION: bool = os.getenv("ENABLE_COMPRESSION", "true").lower() == "true"
    
    # 압축 트리거 (요약된 결과 개수)
    COMPRESSION_THRESHOLD: int = int(os.getenv("COMPRESSION_THRESHOLD", "15"))
    
    # 검색 결과 최대 길이 (자)
    MAX_SNIPPET_LENGTH: int = int(os.getenv("MAX_SNIPPET_LENGTH", "3000"))
    
    # ========== Router 분류 규칙 설정 ==========
    # 규칙 기반 분류 키워드 (하드코딩 제거, 설정으로 관리)
    
    # 트랜잭션 해시 감지 관련
    TRANSACTION_FAQ_KEYWORDS: list = ['출금', '입금', '송금', '이체', '수수료', '한도', '방법', '절차', '가능', '안돼', '안되']
    
    # 시세/가격 질문 키워드
    PRICE_KEYWORDS: list = ['시세', '가격', '현재가', 'price', '시장가', '거래가', '현재 시세', 
                            '현재 가격', '얼마', '실시간', 'realtime', 'current price', 'market price']
    
    # 단순 대화 키워드
    SIMPLE_CHAT_KEYWORDS: list = ['안녕', '하이', '헬로', '고마워', '감사', '고맙', '반가워', '좋아', '네', '응', '그래']
    SIMPLE_CHAT_MAX_LENGTH: int = 20  # 단순 대화로 분류할 최대 길이
    
    # 날짜/시간 질문 키워드
    DATE_TIME_KEYWORDS: list = ['날짜', '날자', '일자', '오늘', '시간', '지금', '현재']
    
    # FAQ 질문 키워드 (명확한 FAQ 질문 감지용)
    FAQ_KEYWORDS: list = ['출금', '입금', '송금', '이체', '수수료', '한도', '방법', '절차', '가능', 
                          '안돼', '안되', '제한', '한계', '비밀번호', '인증', '보안', '계좌', '지갑', 
                          '주소', '해시', '트랜잭션', '거래', '매수', '매도', '주문', '취소', '환불',
                          '도움말', '문의', '고객', '지원', '등록', '해제', '변경', '삭제', '조회']
    
    # 이벤트/프로모션/공지사항 키워드 (web_search로 분류)
    # 주의: '오늘', '이번 주', '이번달'은 DATE_TIME_KEYWORDS와 겹치므로 제외
    EVENT_KEYWORDS: list = ['이벤트', '프로모션', '공지', '공지사항', '안내', '최신', '진행중', 
                            '진행 중', '현재 진행']
    
    # 맥락 의존적 질문 키워드 (대명사/지시어)
    CONTEXT_DEPENDENT_KEYWORDS: list = ['그것', '그거', '그', '이것', '이거', '이', 
                                        '그것에 대해', '그거에 대해', '그에 대해', 
                                        '이것에 대해', '이거에 대해', '이에 대해']
    
    # 독립적인 질문 키워드 (맥락 결합 방지용)
    INDEPENDENT_QUESTION_KEYWORDS: list = ['출금', '입금', '송금', '이체', '수수료', '한도', '방법', 
                                            '절차', '가능', '안돼', '안되', '제한', '한계', '비밀번호', 
                                            '인증', '보안', '계좌', '지갑', '주소', '해시', '트랜잭션', 
                                            '거래', '매수', '매도', '주문', '취소', '환불', '이벤트', 
                                            '프로모션', '공지', '안내', '도움말', '문의', '고객', '지원']
    
    # ========== URL 상수 ==========
    # 빗썸 관련 URL
    BITHUMB_HOME_URL: str = "https://www.bithumb.com"
    BITHUMB_SUPPORT_URL: str = "https://support.bithumb.com/hc/ko"
    BITHUMB_OLD_SUPPORT_URL: str = "https://www.bithumb.com/customer_support/info"  # 사용 금지 (참조용)
    
    # 외부 API URL
    GOOGLE_SEARCH_API_URL: str = "https://www.googleapis.com/customsearch/v1"
    COINMARKETCAP_API_URL: str = "https://pro-api.coinmarketcap.com/v1"
    COINGECKO_API_URL: str = "https://api.coingecko.com/api/v3"
    EXCHANGE_RATE_API_URL: str = "https://api.exchangerate-api.com/v4/latest/USD"
    
    @classmethod
    def get_link_rules_prompt(cls) -> str:
        """링크 사용 규칙 프롬프트 반환"""
        return f"""**링크 사용 규칙 (매우 중요 - 모든 링크에 적용):**
    - **빗썸 고객지원 페이지 링크**: {cls.BITHUMB_SUPPORT_URL}
    - **절대 이전 링크({cls.BITHUMB_OLD_SUPPORT_URL})를 사용하지 마세요.**
    - **⚠️ 절대 마크다운 링크 형식을 사용하지 마세요!**
      * **금지**: `[빗썸 고객지원 페이지]({cls.BITHUMB_SUPPORT_URL}).` ← 이 형식은 절대 사용 금지!
      * **금지**: `[텍스트](URL)` 형식 전체를 사용하지 마세요
      * 마크다운 링크 형식을 사용하면 닫는 괄호가 URL에 포함되어 오류가 발생합니다
    - **올바른 링크 형식 (반드시 이 형식만 사용):**
      * **추천 형식 1 (문장 중간 배치)**: "자세한 정보는 {cls.BITHUMB_SUPPORT_URL} 에서 확인하실 수 있습니다."
      * **추천 형식 2 (별도 문장)**: "빗썸 고객지원 페이지: {cls.BITHUMB_SUPPORT_URL}"
      * **추천 형식 3 (별도 문장)**: "추가 정보: {cls.BITHUMB_SUPPORT_URL}"
      * 형식 4: "{cls.BITHUMB_SUPPORT_URL}" (단독으로 사용 시)
    - **⚠️ 링크 뒤에 마침표가 붙지 않도록 주의하세요:**
      * **잘못된 형식**: "빗썸 고객지원 페이지: {cls.BITHUMB_SUPPORT_URL}." ← 마침표가 URL에 포함됨
      * **올바른 형식**: "빗썸 고객지원 페이지: {cls.BITHUMB_SUPPORT_URL}" (마침표 없음)
      * **또는**: "자세한 정보는 {cls.BITHUMB_SUPPORT_URL} 에서 확인하실 수 있습니다." (링크 뒤 공백 후 문장 계속)
    - **잘못된 형식 (절대 사용 금지):**
      * `[빗썸 고객지원 페이지]({cls.BITHUMB_SUPPORT_URL}).` ← 마크다운 형식, 닫는 괄호가 URL에 포함됨
      * `빗썸 고객지원 페이지({cls.BITHUMB_SUPPORT_URL})` ← 괄호 사용 금지
      * `{cls.BITHUMB_SUPPORT_URL})` ← 닫는 괄호가 URL에 포함됨
      * `{cls.BITHUMB_SUPPORT_URL}.` ← 마침표가 URL에 포함됨
    - **요약: 링크는 항상 일반 텍스트로만 작성하고, 문장 중간에 배치하거나 별도 문장으로 분리하세요. 링크 뒤에 마침표를 직접 붙이지 마세요.**"""
    
    # ========== 기타 설정 ==========
    # 로깅 레벨
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> bool:
        """설정 유효성 검사"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        
        # Google Search를 사용하는 경우 API 키와 CX 확인
        if cls.SEARCH_API.lower() == "google":
            if not cls.GOOGLE_API_KEY:
                logger.warning("Google Search가 선택되었지만 GOOGLE_API_KEY가 설정되지 않았습니다. DuckDuckGo로 대체됩니다.")
            if not cls.GOOGLE_CX:
                logger.warning("Google Search가 선택되었지만 GOOGLE_CX가 설정되지 않았습니다. DuckDuckGo로 대체됩니다.")
        
        return True
    
    @classmethod
    def get_planner_llm_config(cls) -> dict:
        """Planner LLM 설정 반환"""
        model = cls.PLANNER_MODEL or cls._DEFAULT_MODEL
        api_key = cls.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        return {
            "model": model,
            "temperature": cls.PLANNER_TEMPERATURE,
            "openai_api_key": api_key
        }
    
    @classmethod
    def get_writer_llm_config(cls) -> dict:
        """Writer LLM 설정 반환"""
        model = cls.WRITER_MODEL or cls._DEFAULT_MODEL
        api_key = cls.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        return {
            "model": model,
            "temperature": cls.WRITER_TEMPERATURE,
            "openai_api_key": api_key
        }
    
    @classmethod
    def get_summarization_llm_config(cls) -> dict:
        """Summarization LLM 설정 반환"""
        model = cls.SUMMARIZATION_MODEL or cls._DEFAULT_MODEL
        api_key = cls.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        return {
            "model": model,
            "temperature": cls.SUMMARIZATION_TEMPERATURE,
            "openai_api_key": api_key
        }
    
    @classmethod
    def get_compression_llm_config(cls) -> dict:
        """Compression LLM 설정 반환"""
        model = cls.COMPRESSION_MODEL or cls._DEFAULT_MODEL
        api_key = cls.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        return {
            "model": model,
            "temperature": cls.COMPRESSION_TEMPERATURE,
            "openai_api_key": api_key
        }


# 전역 설정 인스턴스
config = ChatbotConfiguration()

