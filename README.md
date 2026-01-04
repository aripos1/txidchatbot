# Multi-Chain Transaction Lookup & Bithumb Chatbot

블록체인 트랜잭션 조회 서비스와 빗썸 거래소 AI 챗봇을 통합한 웹 애플리케이션입니다.

## 주요 기능

- 🔍 **31개 블록체인 네트워크 트랜잭션 조회**: Bitcoin, Ethereum, BNB Smart Chain, Polygon, Solana, Tron 등
- 🤖 **AI 챗봇 (Router-Specialist 아키텍처)**:
  - **Router 노드**: 질문 유형 자동 분류 및 라우팅
  - **Specialist 에이전트**: 
    - `simple_chat`: 단순 대화, 날짜/시간 정보
    - `faq`: FAQ 벡터 검색 + 빗썸 고객지원 페이지 검색
    - `transaction`: 트랜잭션 해시 자동 감지 및 조회
    - `hybrid`: FAQ + 웹 검색 조합
    - `web_search`: Deep Research 워크플로우 (Planner → Researcher → Grader → Writer)
  - **실시간 스트리밍**: Server-Sent Events (SSE) 기반 토큰 스트리밍
  - **생각하는 과정 표시**: 검색 쿼리 및 결과를 사용자에게 시각화
- 📊 **대화 기록 관리**: MongoDB 기반 세션별 대화 저장
- 🐳 **Docker 기반 배포**: AWS EC2 배포 지원

## 빠른 시작

### 사전 요구사항

- Python 3.12 이상
- MongoDB Atlas 계정 (벡터 검색 인덱스 필요)
- OpenAI API 키
- (선택) Google Custom Search API 키

### 로컬 개발 환경 설정

#### 1. 저장소 복제

```bash
git clone https://github.com/aripos1/txidchatbot.git
cd txidchatbot
```

#### 2. 가상 환경 생성 및 활성화

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

또는 `uv`를 사용하는 경우:

```bash
uv venv
source .venv/bin/activate  # Linux/Mac
# Windows: .venv\Scripts\activate
```

#### 3. 의존성 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. 환경 변수 설정

`.env` 파일을 생성하고 다음 변수들을 설정하세요:

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# MongoDB Atlas
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGODB_DATABASE=chatbot_db

# Google Custom Search (선택사항)
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CX=your_google_cx
SEARCH_API=google  # 또는 duckduckgo

# 벡터 검색 설정
SIMILARITY_THRESHOLD=0.7
VECTOR_SEARCH_LIMIT=3

# 로깅
LOG_LEVEL=INFO

# LangSmith 추적 (선택사항 - 모니터링 및 디버깅용)
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=multi-chain-tx-lookup

# 또는 LangChain 환경 변수 사용
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=multi-chain-tx-lookup

# 블록체인 API 키들 (선택사항 - 일부 체인만 필요)
ETHEREUM_API_KEY=...
BNB_SMART_CHAIN_API_KEY=...
POLYGON_API_KEY=...
# ... 기타 체인 API 키들
```

자세한 환경 변수 목록은 [docs/docs.md](docs/docs.md)를 참고하세요.

#### 5. MongoDB Atlas 벡터 검색 인덱스 생성

1. MongoDB Atlas 웹 콘솔에 접속
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

5. 인덱스 이름: `vector_index` (또는 원하는 이름)
6. 대상 컬렉션: `knowledge_base`

#### 6. FAQ 데이터 임포트 (선택사항)

```bash
python scripts/data/import_faq.py
```

#### 7. 서버 실행

**옵션 1: FastAPI 직접 실행 (권장)**
```bash
python main.py
```
서버가 `http://localhost:8000`에서 실행됩니다.

**옵션 2: LangGraph CLI 사용 (개발/디버깅용)**
```bash
# LangGraph CLI 설치 (이미 설치되어 있다면 생략)
pip install langgraph-cli

# LangGraph 개발 서버 실행
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.12 langgraph dev --allow-blocking
```
LangGraph Studio가 `http://localhost:8123`에서 실행됩니다.

> **참고**: LangGraph CLI를 사용하면 LangGraph Studio에서 그래프를 시각화하고 디버깅할 수 있습니다.

### Docker를 사용한 실행

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

## 프로젝트 구조

```
.
├── chatbot/              # 챗봇 관련 모듈
│   ├── graph.py          # LangGraph 워크플로우 (실제 구현)
│   ├── chatbot_graph.py  # 하위 호환성 래퍼
│   ├── configuration.py  # 설정 관리
│   ├── models.py         # 타입 정의 (ChatState, QuestionType 등)
│   ├── mongodb_client.py # MongoDB 연결
│   ├── vector_store.py   # 벡터 검색
│   ├── nodes/            # 노드 구현
│   │   ├── router.py     # 질문 분류 및 라우팅
│   │   ├── intent_clarifier.py  # 의도 명확화
│   │   ├── specialists/  # 전문가 에이전트
│   │   │   ├── simple_chat.py
│   │   │   ├── faq.py
│   │   │   ├── transaction.py
│   │   │   ├── hybrid.py
│   │   └── deep_research/  # Deep Research 워크플로우
│   │       ├── planner.py
│   │       ├── researcher.py
│   │       ├── grader.py
│   │       ├── summarizer.py
│   │       └── check_db.py
│   └── prompts/          # 프롬프트 템플릿
├── src/                  # 트랜잭션 조회 서비스
│   └── services/
│       ├── transaction_service.py  # 트랜잭션 감지 및 조회
│       └── chain_configs.py        # 31개 체인 설정
├── scripts/              # 유틸리티 스크립트
│   ├── data/            # 데이터 관리
│   │   ├── import_faq.py
│   │   ├── setup_vector_db.py
│   │   └── crawl_bithumb.py
│   └── deploy/          # 배포 스크립트
├── docs/                 # 문서
│   ├── docs.md          # 전체 개발 문서
│   ├── ROUTER_SPECIALIST_ARCHITECTURE.md
│   └── ...
├── templates/            # HTML 템플릿
│   └── chatbot.html     # 챗봇 UI (스트리밍 지원)
├── main.py              # FastAPI 애플리케이션
├── requirements.txt     # Python 의존성
├── langgraph.json      # LangGraph CLI 설정
└── docker-compose.yml   # Docker Compose 설정
```

## API 엔드포인트

### 챗봇 API

**POST /api/chat**
```json
{
  "message": "입금이 안돼요",
  "session_id": "session_123",
  "debug": true
}
```

**응답:**
```json
{
  "response": "AI 답변...",
  "session_id": "session_123",
  "debug": {
    "similarity_scores": [...],
    "needs_deep_research": false
  }
}
```

**POST /api/chat/stream** (스트리밍)
- Server-Sent Events (SSE) 기반 실시간 토큰 스트리밍
- "생각하는 과정" 정보 포함
- 이벤트 타입: `token`, `node`, `node_search`, `done`

**요청:**
```json
{
  "message": "빗썸 이벤트 알려줘",
  "session_id": "session_123"
}
```

**응답 (SSE 스트림):**
```
event: token
data: {"type": "token", "content": "현재"}

event: node
data: {"type": "node", "node": "planner", "status": "running"}

event: node_search
data: {"type": "node_search", "node": "researcher", "queries": [...], "db_results": [...], "web_results": [...]}

event: done
data: {"type": "done"}
```

### 트랜잭션 조회 API

**GET /api/tx/{txid}**
- 트랜잭션 해시 자동 감지 (31개 체인 지원)
- 자동으로 적절한 체인 API 호출

**GET /api/chains**
- 지원하는 모든 체인 목록 반환

### 대화 기록

- **GET /api/chat/history/{session_id}**: 대화 기록 조회
- **DELETE /api/chat/history/{session_id}**: 대화 기록 삭제

### 기타

- **GET /chat**: 챗봇 UI 페이지
- **GET /**: 트랜잭션 조회 UI 페이지
- **GET /health**: 헬스 체크

자세한 API 문서는 [docs/docs.md](docs/docs.md)를 참고하세요.

## 시스템 아키텍처

### Router-Specialist 아키텍처

```
사용자 질문
    ↓
Router (질문 분류)
    ├─ simple_chat → save_response → END
    ├─ faq → save_response → END
    ├─ transaction → save_response → END
    ├─ hybrid → (planner 또는 writer) → ...
    └─ web_search → planner → researcher → grader
                        ↑                      ↓
                        └── (점수 < 0.7, 3회 미만) ─┘
                        ↓ (점수 ≥ 0.7 또는 3회 이상)
                    writer → save_response → END
```

### 질문 유형

- `simple_chat`: 단순 대화, 인사, 날짜/시간 질문
- `faq`: FAQ 데이터베이스 답변 (벡터 검색)
- `transaction`: 트랜잭션 해시 조회 (31개 체인 자동 감지)
- `web_search`: 최신 정보 필요 (이벤트, 공지사항) - Deep Research 워크플로우
- `hybrid`: FAQ + 웹 검색 조합
- `intent_clarification`: 의도 명확화 필요
- `general`: 일반 문의 (기본값, FAQ로 처리)

### 지원하는 블록체인 (31개)

**Bitcoin 계열:**
- Bitcoin, Litecoin, Dogecoin

**Ethereum 계열 (EVM):**
- Ethereum, BNB Smart Chain, Polygon, Arbitrum, Optimism, Avalanche, Base, Mantle, Blast, Scroll, Linea, zkSync Era, World Chain, Swell L2, KAIA, Cronos, Sophon, WEMIX, Endurance, Ethereum Classic

**기타:**
- Tron, Solana, TON, Ripple, Stellar, Injective, Cosmos Hub, XPLA, Stacks

## 배포

### AWS EC2 배포

```bash
# 배포 스크립트 실행
./deploy.sh

# 또는 수동 배포
docker-compose build --no-cache
docker-compose up -d
```

자세한 배포 가이드는 [docs/docs.md](docs/docs.md)의 "7. 배포" 섹션을 참고하세요.

## 개발 문서

- [전체 개발 문서](docs/docs.md)
- [Router-Specialist 아키텍처](docs/ROUTER_SPECIALIST_ARCHITECTURE.md)
- [스트리밍 개선 사항](docs/STREAMING_IMPROVEMENTS.md)
- [LangGraph 1.0 업그레이드](docs/LANGGRAPH_1.0_REVIEW.md)
- [AWS 로그 확인 가이드](docs/AWS_LOG_GUIDE.md)
- [디버그 모드 가이드](docs/DEBUG_MODE_GUIDE.md)
- [점수 확인 가이드](docs/SCORE_CHECK_GUIDE.md)

## 기술 스택

- **Backend**: FastAPI, Python 3.12
- **AI/ML**: LangGraph 1.0+, LangChain 1.0+, OpenAI
- **Database**: MongoDB Atlas (Vector Search)
- **Containerization**: Docker, Docker Compose
- **Deployment**: AWS EC2
- **Frontend**: HTML, JavaScript (Server-Sent Events)

## 주요 특징

- ✅ **실시간 스트리밍**: SSE 기반 토큰 스트리밍으로 빠른 응답
- ✅ **생각하는 과정 표시**: 검색 쿼리 및 결과를 사용자에게 시각화
- ✅ **31개 체인 지원**: 대부분의 주요 블록체인 네트워크 지원
- ✅ **스마트 라우팅**: 질문 유형에 따른 자동 분류 및 전문가 에이전트 라우팅
- ✅ **Deep Research**: 검색 결과 평가 및 재검색 루프를 통한 고품질 답변
- ✅ **벡터 검색**: MongoDB Atlas 벡터 검색으로 정확한 FAQ 매칭

## 라이선스

이 프로젝트는 개인 프로젝트입니다.

## 기여

이슈 및 풀 리퀘스트를 환영합니다!
