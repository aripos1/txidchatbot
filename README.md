# AI Chatbot Platform - LangGraph Multi-Agent System

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-green.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-1.0+-purple.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1+-teal.svg)

**LangGraph 기반 멀티 에이전트 AI 챗봇 플랫폼**

[아키텍처](#-아키텍처) • [빠른 시작](#-빠른-시작) • [설정](#-설정)

</div>

---

## 📋 목차

- [프로젝트 개요](#-프로젝트-개요)
- [아키텍처](#-아키텍처)
- [빠른 시작](#-빠른-시작)
- [설정](#-설정)
- [프로젝트 구조](#-프로젝트-구조)
- [API 문서](#-api-문서)

---

## 🎯 프로젝트 개요

**LangGraph 기반 멀티 에이전트 AI 챗봇**은 Router-Specialist 아키텍처를 사용하여 질문을 분류하고 적절한 전문가 에이전트로 라우팅하는 지능형 챗봇 시스템입니다.

### 핵심 특징

- 🤖 **멀티 에이전트 시스템**: CoordinatorAgent가 여러 Specialist 에이전트를 조율
- 🔀 **Router-Specialist 아키텍처**: 질문 유형에 따라 최적의 전문가 선택
- 🔄 **Deep Research 워크플로우**: Planner → Researcher → Grader → Writer 순환 구조
- ⚡ **실시간 스트리밍**: Server-Sent Events (SSE) 기반 토큰 스트리밍
- 🔍 **벡터 검색**: MongoDB Atlas 벡터 검색으로 FAQ 검색
- 📊 **구조화된 출력**: Pydantic 모델을 사용한 타입 안전성

### 기술 스택

| 카테고리 | 기술 |
|---------|------|
| **AI Framework** | LangGraph 1.0+, LangChain 1.0+ |
| **LLM** | OpenAI GPT-4o-mini |
| **Backend** | FastAPI 0.104.1+, Uvicorn |
| **Database** | MongoDB Atlas (벡터 검색) |
| **Streaming** | Server-Sent Events (SSE) |

---

## 🏗️ 아키텍처

### LangGraph 워크플로우

```
사용자 질문
    ↓
Coordinator (라우팅 포함, 멀티 에이전트 모드)
    ↓
┌──────────┬──────────┬──────────┬──────────┐
│ Simple   │   FAQ    │Transaction│   Deep   │
│  Chat    │ Specialist│Specialist│ Research │
└──────────┴──────────┴──────────┴──────────┘
                              ↓
                    ┌─────────────────┐
                    │  Deep Research  │
                    │  (순환 구조)    │
                    └─────────────────┘
                              ↓
                    Planner → Researcher
                              ↓
                    Grader (평가)
                              ↓
                    ┌─────────┴─────────┐
                    │ 충분함? │ 부족함? │
                    └─────────┴─────────┘
                         ↓         ↓
                      Writer    Planner (재검색)
                         ↓
                    Save Response
```

### 멀티 에이전트 시스템

**현재 모드:** `USE_TRUE_MULTI_AGENT=true`

- CoordinatorAgent가 엔트리 포인트로 등록됨
- CoordinatorAgent가 Router 로직을 직접 실행하여 라우팅 처리
- 모든 에이전트가 LangGraph 노드로 등록되어 순차적으로 호출됨
- LangGraph의 조건부 엣지를 통해 워크플로우 관리
- Server-Sent Events (SSE) 지원으로 실시간 스트리밍 가능

**에이전트 구조:**

```python
BaseAgent (추상 클래스)
├── CoordinatorAgent: 멀티 에이전트 협업 관리
├── RouterAgent: 질문 분류 및 라우팅
├── SimpleChatAgent: 단순 대화 처리
├── FAQAgent: FAQ 벡터 검색
├── TransactionAgent: 트랜잭션 해시 조회
├── PlannerAgent: 검색 계획 수립
├── ResearcherAgent: 웹 검색 수행
└── GraderAgent: 검색 결과 평가
```

### Deep Research 워크플로우

**순환형 구조 (Self-Correcting Loop):**

1. **Planner**: 사용자 질문 분석 → 검색 쿼리 생성 (5-7개)
2. **Researcher**: 병렬 웹 검색 (Google + DuckDuckGo + Tavily)
3. **Grader**: 검색 결과 평가 (0.0-1.0 점수)
4. **조건부 라우팅**:
   - 점수 ≥ 0.7 → **Writer** (답변 생성)
   - 점수 < 0.7 → **Planner** (재검색, 최대 3회)
   - 반복 3회 초과 → **Writer** (Fallback)

**구조화된 출력:**
- `SearchPlan`: 검색 쿼리 목록 및 연구 계획
- `GraderResult`: 평가 점수, 충분 여부, 피드백

### Specialist 에이전트

| Specialist | 역할 | 기술 |
|-----------|------|------|
| **Simple Chat** | 단순 대화, 인사 | GPT-4o-mini |
| **FAQ** | FAQ 벡터 검색 | MongoDB Vector Search |
| **Transaction** | 트랜잭션 해시 조회 | Multi-chain API |
| **Deep Research** | 복잡한 질문 심층 연구 | Planner → Researcher → Grader → Writer |

### Server-Sent Events (SSE) 스트리밍

**이벤트 타입:**
- `start`: 세션 시작
- `node`: 노드 실행 상태 (예: "🔀 라우팅 중...")
- `token`: LLM 출력 토큰 스트리밍
- `node_search`: 검색 정보 (쿼리, 결과, 링크)
- `done`: 완료 (최종 응답)
- `error`: 오류 발생

**스트리밍 노드:**
- `writer`, `simple_chat_specialist`, `faq_specialist`, `transaction_specialist`, `intent_clarifier`

---

## 🚀 빠른 시작

### 사전 요구사항

- Python 3.12+
- MongoDB Atlas (벡터 검색 인덱스 필요)
- OpenAI API 키

### 설치

```bash
# 저장소 클론
git clone <repository-url>
cd multi-chain-tx-lookup/app

# 가상 환경 생성
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 환경 변수 설정

`.env` 파일 생성:

```bash
# 필수
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
MONGODB_URI=mongodb+srv://...
MONGODB_DATABASE=chatbot_db

# 멀티 에이전트 모드
USE_TRUE_MULTI_AGENT=true

# 검색 API (선택)
SEARCH_API=google  # 또는 duckduckgo
GOOGLE_API_KEY=...
GOOGLE_CX=...
TAVILY_API_KEY=...

# LangSmith 추적 (선택)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=multi-chain-tx-lookup
```

### MongoDB 벡터 검색 인덱스

MongoDB Atlas에서 벡터 검색 인덱스 생성:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    }
  ]
}
```

### 실행

```bash
# 개발 모드
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 프로덕션 모드
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

서버가 `http://localhost:8000`에서 실행됩니다.

---

## ⚙️ 설정

### LLM 모델 설정

```bash
# Planner (검색 계획 수립)
PLANNER_MODEL=gpt-4o-mini
PLANNER_TEMPERATURE=0.3

# Writer (답변 작성)
WRITER_MODEL=gpt-4o-mini
WRITER_TEMPERATURE=0.7

# Grader (결과 평가)
GRADER_MODEL=gpt-4o-mini
GRADER_TEMPERATURE=0.1
```

### 벡터 검색 설정

```bash
SIMILARITY_THRESHOLD=0.7
VECTOR_SEARCH_LIMIT=3
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### 하이브리드 검색 설정

하이브리드 검색은 벡터 검색(시맨틱)과 키워드 검색(BM25/Lexical)을 결합하여 더 정확한 검색 결과를 제공합니다.

```bash
# 키워드 검색 가중치 (0.0 ~ 1.0)
HYBRID_K_WEIGHT=0.7

# 시맨틱 검색 가중치 (0.0 ~ 1.0)
HYBRID_S_WEIGHT=0.3

# 최종 검색 결과 개수
FINAL_TOP_K=5
```

**설명:**
- 하이브리드 검색은 가중치 결합 방식을 사용합니다.
- 키워드 검색 70%, 시맨틱 검색 30% 가중치로 결과를 통합합니다.
- FAQ 검색에서 자동으로 하이브리드 검색이 수행됩니다.

### 검색 설정

```bash
MAX_SEARCH_QUERIES=7
MAX_SEARCH_RESULTS=20
MAX_RESULTS_PER_QUERY=8
```

### Deep Research 설정

```bash
# 요약/압축 활성화
ENABLE_SUMMARIZATION=true
ENABLE_COMPRESSION=true
SUMMARIZATION_THRESHOLD=10
COMPRESSION_THRESHOLD=15
```

---

## 📁 프로젝트 구조

```
app/
├── chatbot/                    # AI 챗봇 모듈
│   ├── graph.py               # LangGraph 워크플로우 정의
│   ├── models.py             # ChatState, 구조화된 출력 모델
│   ├── configuration.py      # 설정 관리
│   ├── agents/               # 멀티 에이전트 시스템
│   │   ├── base_agent.py    # BaseAgent 추상 클래스
│   │   ├── coordinator_agent.py
│   │   ├── router_agent.py
│   │   ├── specialist_agents.py
│   │   └── deep_research_agents.py
│   ├── nodes/                # LangGraph 노드
│   │   ├── router.py        # 질문 분류
│   │   ├── specialists/     # Specialist 노드
│   │   └── deep_research/   # Deep Research 워크플로우
│   │       ├── planner.py
│   │       ├── researcher.py
│   │       ├── grader.py
│   │       └── writer.py
│   ├── vector_store.py       # MongoDB 벡터 검색
│   └── mongodb_client.py     # MongoDB 연결
├── src/
│   └── routers/
│       └── chat.py          # SSE 스트리밍 엔드포인트
└── main.py                  # FastAPI 애플리케이션
```

---

## 📡 API 문서

### 챗봇 스트리밍 API

```http
POST /api/chat/stream
Content-Type: application/json

{
  "message": "비트코인 시세 알려줘",
  "session_id": "unique_session_id"
}
```

**SSE 응답 형식:**
```
data: {"type": "start", "session_id": "..."}
data: {"type": "node", "node": "router", "display": "🔀 라우팅 중..."}
data: {"type": "token", "content": "비트코인"}
data: {"type": "node_search", "node": "researcher", "searchInfo": {...}}
data: {"type": "done", "final_response": "..."}
```

### 대화 기록 조회

```http
GET /api/chat/history/{session_id}
```

### 대화 기록 삭제

```http
DELETE /api/chat/history/{session_id}
```

---

## 🔧 주요 기능

### 1. 질문 분류 (Router)

- 규칙 기반 분류 (키워드 매칭)
- LLM 기반 분류 (구조화된 출력)
- 질문 유형: `simple_chat`, `faq`, `transaction`, `web_search`, `hybrid`

### 2. FAQ 벡터 검색

- MongoDB Atlas 벡터 검색
- 유사도 임계값 기반 필터링
- 하이브리드 검색 (키워드 + 벡터)

### 3. Deep Research

- **Planner**: 검색 쿼리 생성 (5-7개)
- **Researcher**: 병렬 웹 검색 (Google + DuckDuckGo + Tavily)
- **Grader**: 결과 평가 (0.0-1.0 점수)
- **Writer**: 최종 답변 생성
- **자기 수정 루프**: 점수 부족 시 자동 재검색 (최대 3회)

### 4. 실시간 스트리밍

- 노드별 진행 상황 표시
- LLM 토큰 스트리밍
- 검색 정보 시각화
- "Thinking Process" 섹션 (검색 쿼리, 결과, 링크)

---

## 🛠️ 개발 가이드

### 코드 스타일

- **Python**: PEP 8 준수
- **타입 힌팅**: 모든 함수에 타입 힌팅
- **비동기 처리**: I/O 작업은 `async/await` 사용

### LangGraph 노드 추가

```python
from chatbot.models import ChatState
from chatbot.graph import create_chatbot_graph

async def my_node(state: ChatState) -> ChatState:
    # 노드 로직
    return state

# graph.py에서 노드 등록
workflow.add_node("my_node", my_node)
```

### 에이전트 추가

```python
from chatbot.agents.base_agent import BaseAgent
from chatbot.models import ChatState

class MyAgent(BaseAgent):
    async def process(self, state: ChatState) -> ChatState:
        # 에이전트 로직
        return state
```

---

## 📚 참고 자료

- [LangGraph 문서](https://langchain-ai.github.io/langgraph/)
- [LangChain 문서](https://python.langchain.com/)
- [FastAPI 문서](https://fastapi.tiangolo.com/)

---

<div align="center">

**Made with ❤️ by Multi Chain Explorer Team**

</div>
