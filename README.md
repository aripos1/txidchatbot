# Multi-Chain Transaction Lookup & AI Chatbot Platform

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1+-teal.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

**31개 블록체인 네트워크 트랜잭션 조회 및 AI 챗봇 통합 플랫폼**

[기능](#-주요-기능) • [설치](#-빠른-시작) • [사용 가이드](#-사용-가이드)

</div>

---

## 📋 목차

- [프로젝트 개요](#-프로젝트-개요)
- [주요 기능](#-주요-기능)
- [아키텍처](#-아키텍처)
- [빠른 시작](#-빠른-시작)
- [설치 및 설정](#-설치-및-설정)
- [사용 가이드](#-사용-가이드)
- [API 문서](#-api-문서)
- [배포](#-배포)
- [개발 가이드](#-개발-가이드)
- [문제 해결](#-문제-해결)
- [기여하기](#-기여하기)
- [라이선스](#-라이선스)

---

## 🎯 프로젝트 개요

**Multi-Chain Transaction Lookup & AI Chatbot Platform**은 블록체인 트랜잭션 조회 서비스와 AI 기반 챗봇을 통합한 엔터프라이즈급 웹 애플리케이션입니다.

### 핵심 가치

- 🔍 **멀티체인 지원**: 31개 블록체인 네트워크 동시 조회
- 🤖 **지능형 AI 챗봇**: Router-Specialist 아키텍처 기반 전문가 시스템
- ⚡ **실시간 스트리밍**: Server-Sent Events 기반 토큰 스트리밍
- 🔒 **엔터프라이즈 보안**: MongoDB Atlas 벡터 검색 및 안전한 세션 관리
- 📱 **반응형 디자인**: 모바일 최적화된 사용자 인터페이스

### 기술 스택

| 카테고리 | 기술 |
|---------|------|
| **Backend** | FastAPI 0.104.1+, Uvicorn 0.24.0+ |
| **AI/ML** | LangGraph 1.0+, LangChain 1.0+, OpenAI GPT-4o-mini |
| **Database** | MongoDB Atlas (벡터 검색 지원) |
| **Frontend** | Jinja2, Vanilla JavaScript, CSS3 |
| **Deployment** | Docker, AWS EC2, Nginx |

---

## ✨ 주요 기능

### 1. 멀티체인 트랜잭션 조회

**31개 블록체인 네트워크 지원**

- **Bitcoin 계열**: Bitcoin, Litecoin, Dogecoin
- **Ethereum 계열 (EVM)**: Ethereum, BNB Smart Chain, Polygon, Arbitrum, Optimism, Avalanche, Base, Mantle, Blast, Scroll, Linea, zkSync Era, World Chain, Swell L2, KAIA, Cronos, Sophon, WEMIX, Endurance, Ethereum Classic
- **기타 네트워크**: Tron, Solana, TON, Ripple, Stellar, Injective, Cosmos Hub, XPLA, Stacks

**주요 특징:**
- 자동 네트워크 감지
- 동시 다중 네트워크 검색
- 실시간 트랜잭션 상태 확인
- 블록 탐색기 직접 링크 제공

### 2. AI 챗봇 (Router-Specialist 아키텍처)

**지능형 질문 분류 및 라우팅**

```
사용자 질문
    ↓
Router Node (질문 유형 분류)
    ↓
┌──────────┬──────────┬──────────┬──────────┐
│ Simple   │   FAQ    │Transaction│   Deep   │
│  Chat    │ Specialist│Specialist│ Research │
└──────────┴──────────┴──────────┴──────────┘
```

**Specialist 에이전트:**

| Specialist | 역할 | 기술 스택 |
|-----------|------|----------|
| **Simple Chat** | 단순 대화, 날짜/시간 정보 | GPT-4o-mini |
| **FAQ Specialist** | FAQ 벡터 검색 + 빗썸 고객지원 검색 | MongoDB Vector Search, BeautifulSoup4 |
| **Transaction Specialist** | 트랜잭션 해시 자동 감지 및 조회 | Multi-chain API Integration |
| **Deep Research** | 복잡한 질문에 대한 심층 연구 | Planner → Researcher → Grader → Writer |

**실시간 스트리밍:**
- Server-Sent Events (SSE) 기반 토큰 스트리밍
- 노드별 진행 상황 실시간 표시
- 검색 쿼리 및 결과 시각화

### 3. 콘텐츠 관리 시스템

**블로그 카테고리 분류:**

| 카테고리 | 설명 | 포스트 수 |
|---------|------|----------|
| **기초 가이드** | 블록체인 기본 개념 및 입문 | 1 |
| **트랜잭션** | 트랜잭션 구조 및 작동 원리 | 1 |
| **스마트 컨트랙트** | 스마트 컨트랙트 개발 및 활용 | 1 |
| **멀티체인** | 다양한 블록체인 네트워크 비교 | 1 |
| **DeFi** | 탈중앙화 금융 서비스 | 1 |
| **보안** | 블록체인 보안 및 모범 사례 | 1 |
| **레이어 2** | 확장성 솔루션 (Polygon, Arbitrum 등) | 1 |
| **NFT** | 대체 불가능한 토큰 가이드 | 1 |

**SEO 최적화:**
- 메타 태그 최적화
- 구조화된 데이터 (Schema.org)
- 사이트맵 및 robots.txt
- Google AdSense 통합

---

## 🏗️ 아키텍처

### 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend Layer                       │
│  (Jinja2 Templates + Vanilla JavaScript + CSS)        │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    API Gateway Layer                    │
│              (FastAPI + Uvicorn)                        │
└─────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴───────────────────┐
        ↓                                       ↓
┌───────────────────┐              ┌───────────────────┐
│ Transaction       │              │  AI Chatbot      │
│ Service           │              │  (LangGraph)      │
│                   │              │                   │
│ - Chain Detection │              │ - Router          │
│ - Multi-chain     │              │ - Specialists     │
│   Query           │              │ - Streaming       │
└───────────────────┘              └───────────────────┘
        ↓                                       ↓
┌─────────────────────────────────────────────────────────┐
│                    Data Layer                           │
│  MongoDB Atlas (Vector Search + Conversation History)    │
└─────────────────────────────────────────────────────────┘
```

### LangGraph 워크플로우

```python
# Router-Specialist 아키텍처
graph = StateGraph(ChatState)
    .add_node("router", route_question)
    .add_node("simple_chat_specialist", handle_simple_chat)
    .add_node("faq_specialist", search_faq)
    .add_node("transaction_specialist", lookup_transaction)
    .add_node("planner", create_research_plan)
    .add_node("researcher", web_search)
    .add_node("grader", evaluate_results)
    .add_node("writer", generate_response)
```

---

## 🚀 빠른 시작

### 사전 요구사항

- **Python**: 3.12 이상
- **MongoDB Atlas**: 벡터 검색 인덱스 필요
- **OpenAI API 키**: 필수
- **Docker** (선택사항): 컨테이너 배포용

### 1분 안에 시작하기

```bash
# 저장소 클론 (실제 저장소 URL로 변경 필요)
# git clone <your-repository-url>
# cd multi-chain-tx-lookup

# 가상 환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
# .env 파일을 생성하고 API 키를 설정하세요

# 서버 실행
python main.py
```

서버가 `http://localhost:8000`에서 실행됩니다.

---

## 📦 설치 및 설정

### 상세 설치 가이드

#### 1. 저장소 복제

```bash
# 실제 저장소 URL로 변경 필요
# git clone <your-repository-url>
# cd multi-chain-tx-lookup
```

#### 2. 가상 환경 설정

**Python venv 사용:**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

**uv 사용 (권장):**
```bash
uv venv
source .venv/bin/activate
```

#### 3. 의존성 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. 환경 변수 설정

`.env` 파일을 생성하고 다음 변수들을 설정하세요:

```bash
# ============================================
# 필수 환경 변수
# ============================================

# OpenAI API (필수)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# MongoDB Atlas (필수)
MONGODB_URI=your_mongodb_connection_string
MONGODB_DATABASE=your_database_name

# ============================================
# 선택적 환경 변수
# ============================================

# 검색 API 설정
SEARCH_API=google  # 또는 duckduckgo
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CX=your_google_cx

# 벡터 검색 설정
SIMILARITY_THRESHOLD=0.7
VECTOR_SEARCH_LIMIT=3

# LLM 모델 설정
PLANNER_MODEL=gpt-4o-mini
PLANNER_TEMPERATURE=0.3
WRITER_MODEL=gpt-4o-mini
WRITER_TEMPERATURE=0.7

# 로깅
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# LangSmith 추적 (선택사항)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=multi-chain-tx-lookup
```

#### 5. MongoDB Atlas 벡터 검색 인덱스 생성

1. MongoDB Atlas 웹 콘솔 접속
2. Database → 클러스터 선택 → Search 탭
3. "Create Search Index" 클릭
4. JSON Editor 선택 후 다음 인덱스 정의 입력:

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

5. 인덱스 이름과 컬렉션 이름은 프로젝트 설정에 맞게 지정하세요

#### 6. FAQ 데이터 임포트 (선택사항)

```bash
python scripts/data/import_faq.py
```

---

## 📖 사용 가이드

### 웹 인터페이스

**프로덕션 환경:**
- 트랜잭션 조회: https://txid.shop/
- AI 챗봇: https://txid.shop/chat
- 블로그: https://txid.shop/blog
- 이용가이드: https://txid.shop/guide

**로컬 개발 환경:**
```bash
python main.py
# 또는
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 트랜잭션 조회 사용법

1. 홈페이지 검색창에 트랜잭션 해시 입력
2. 자동으로 31개 네트워크에서 검색
3. 결과에서 해당 네트워크 확인 및 블록 탐색기로 이동

### AI 챗봇 사용법

**질문 예시:**
- FAQ: "원화 출금 방법 알려줘"
- 시세: "오늘 비트코인, 이더리움 시세 알려줘"
- 트랜잭션: "0x1234... 트랜잭션 정보 알려줘"
- 이벤트: "최근 진행중인 이벤트 알려줘"

**실시간 스트리밍:**
- 질문 입력 후 실시간으로 응답 생성 과정 확인
- 검색 쿼리 및 결과 자동 표시
- 노드별 진행 상황 시각화

---

## 📡 API 문서

### 엔드포인트 목록

#### 트랜잭션 조회

```http
GET /api/tx/{txid}
```

**응답 예시:**
```json
{
  "found": true,
  "results": [
    {
      "chain": "ethereum",
      "name": "Ethereum",
      "explorer": "https://etherscan.io/tx/0x..."
    }
  ]
}
```

#### 챗봇 스트리밍 API

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
data: {"type": "done", "final_response": "..."}
```

#### 대화 기록 조회

```http
GET /api/chat/history/{session_id}
```

#### 대화 기록 삭제

```http
DELETE /api/chat/history/{session_id}
```

### API 사용 예시

**Python:**
```python
import httpx

# 트랜잭션 조회
response = httpx.get("http://localhost:8000/api/tx/0x...")
print(response.json())

# 챗봇 스트리밍
async with httpx.AsyncClient() as client:
    async with client.stream(
        "POST",
        "http://localhost:8000/api/chat/stream",
        json={"message": "비트코인 시세", "session_id": "test"}
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                print(line[6:])
```

**cURL:**
```bash
# 트랜잭션 조회
curl http://localhost:8000/api/tx/0x1234567890abcdef...

# 챗봇 스트리밍
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "비트코인 시세", "session_id": "test"}'
```

---

## 🚢 배포

### Docker를 사용한 배포

#### 1. Docker Compose로 실행

```bash
docker-compose up -d
```

#### 2. 로그 확인

```bash
docker-compose logs -f web
```

#### 3. 컨테이너 중지

```bash
docker-compose down
```

### AWS EC2 배포

#### 1. AWS CodeDeploy 사용 (권장)

`appspec.yml` 파일이 설정되어 있으면 AWS CodeDeploy가 자동으로 다음 스크립트를 실행합니다:

- `before_install.sh`: 배포 전 준비 (디렉토리 생성, 기존 애플리케이션 중지)
- `after_install.sh`: 배포 후 설정 (SSL 인증서 자동 갱신 설정)
- `start_application.sh`: 애플리케이션 시작 (Docker Compose)

**CodeDeploy 배포:**
```bash
# CodeDeploy를 통해 배포하면 스크립트가 자동으로 실행됩니다
aws deploy create-deployment \
  --application-name multi-chain-tx-lookup \
  --deployment-group-name production \
  --s3-location bucket=your-bucket,key=deploy.zip,bundleType=zip
```

#### 2. 수동 배포 (CodeDeploy 미사용 시)

CodeDeploy를 사용하지 않는 경우, 스크립트를 수동으로 실행할 수 있습니다:

```bash
# 배포 전 스크립트 (디렉토리 생성, 기존 애플리케이션 중지)
sudo ./scripts/deploy/before_install.sh

# 배포 후 스크립트 (SSL 인증서 자동 갱신 설정)
sudo ./scripts/deploy/after_install.sh

# 애플리케이션 시작 (Docker Compose)
sudo ./scripts/deploy/start_application.sh
```

**참고:** 
- CodeDeploy를 사용하는 경우 스크립트는 자동으로 실행되므로 수동 실행이 필요 없습니다.
- 수동 배포 시에는 스크립트 실행 순서를 지켜야 합니다.

### 프로덕션 환경 변수

프로덕션 환경에서는 다음 환경 변수를 반드시 설정하세요:

```bash
# 보안 관련 환경 변수는 프로덕션 환경에 맞게 설정하세요
# 성능 및 모니터링 설정도 환경에 맞게 구성하세요
```

---

## 🛠️ 개발 가이드

### 프로젝트 구조

```
multi-chain-tx-lookup/
├── chatbot/                    # AI 챗봇 모듈
│   ├── graph.py               # LangGraph 워크플로우
│   ├── configuration.py       # 설정 관리
│   ├── models.py             # 타입 정의
│   ├── mongodb_client.py     # MongoDB 연결
│   ├── vector_store.py       # 벡터 검색
│   ├── nodes/                # LangGraph 노드
│   │   ├── router.py        # 질문 분류
│   │   ├── specialists/     # 전문가 에이전트
│   │   └── deep_research/   # 심층 연구 워크플로우
│   └── prompts/             # 프롬프트 템플릿
├── src/                      # 트랜잭션 서비스
│   └── services/
│       ├── transaction_service.py
│       └── chain_configs.py
├── templates/               # HTML 템플릿
├── static/                  # 정적 파일
├── scripts/                # 유틸리티 스크립트
├── docs/                   # 문서
├── tests/                  # 테스트
└── main.py                # FastAPI 애플리케이션
```

### 개발 환경 설정

```bash
# 개발 모드로 실행 (자동 리로드)
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 디버그 모드
LOG_LEVEL=DEBUG python main.py
```

### 코드 스타일

- **Python**: PEP 8 준수
- **타입 힌팅**: 모든 함수에 타입 힌팅 추가
- **문서화**: 모든 공개 함수/클래스에 docstring 추가
- **비동기 처리**: I/O 작업은 반드시 `async/await` 사용

### 테스트 실행

```bash
# 전체 테스트 실행
python -m pytest tests/

# 특정 테스트 실행
python -m pytest tests/test_logging.py -v
```

---

## 🔧 문제 해결

### 일반적인 문제

#### MongoDB 연결 실패

**증상:** "MongoDB 연결 실패" 오류

**해결 방법:**
1. `.env` 파일의 `MONGODB_URI` 확인
2. MongoDB Atlas IP 화이트리스트 확인
3. 네트워크 연결 확인

#### OpenAI API 오류

**증상:** "OpenAI API 키가 설정되지 않았습니다"

**해결 방법:**
1. `.env` 파일에 `OPENAI_API_KEY` 설정 확인
2. API 키 유효성 확인
3. API 사용량 한도 확인

#### 벡터 검색 인덱스 오류

**증상:** FAQ 검색이 작동하지 않음

**해결 방법:**
1. MongoDB Atlas에서 벡터 검색 인덱스 생성 확인
2. 환경 변수에 설정된 인덱스 이름 확인
3. 환경 변수에 설정된 컬렉션 이름 확인

### 디버그 모드

```bash
# 로그 레벨 설정
LOG_LEVEL=DEBUG python main.py

# LangSmith 추적 활성화 (선택사항)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
```

### 로그 확인

```bash
# Docker 로그
docker-compose logs -f web

# 시스템 로그
journalctl -u multi-chain-tx-lookup -f
```

---

## 🤝 기여하기

프로젝트 개선을 위한 제안이나 버그 리포트를 환영합니다.

### 기여 가이드라인

- 코드 스타일: PEP 8 준수
- 테스트: 새로운 기능에 대한 테스트 추가
- 문서화: 코드 변경사항 문서화
- 커밋 메시지: 명확하고 간결하게 작성

---

## 🙏 감사의 말

이 프로젝트는 다음 오픈소스 프로젝트들을 사용합니다:

- [FastAPI](https://fastapi.tiangolo.com/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [LangChain](https://python.langchain.com/)
- [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)

---

<div align="center">

**Made with ❤️ by Multi Chain Explorer Team**

[웹사이트](https://txid.shop) • [문의사항](https://txid.shop/contact)

</div>
