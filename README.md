# Multi-Chain Transaction Lookup & Bithumb Chatbot

블록체인 트랜잭션 조회 서비스와 빗썸 거래소 AI 챗봇을 통합한 웹 애플리케이션입니다.

**버전**: v1.0.0

## 📋 목차

- [주요 기능](#주요-기능)
- [프로젝트 구성](#프로젝트-구성)
- [설치 방법](#설치-방법)
- [사용법](#사용법)
- [버그 및 디버그](#버그-및-디버그)
- [참고 및 출처](#참고-및-출처)
- [업데이트 정보](#업데이트-정보)
- [저작권](#저작권)

## 주요 기능

- 🔍 **31개 블록체인 네트워크 트랜잭션 조회**: Bitcoin, Ethereum, BNB Smart Chain, Polygon, Solana, Tron 등
- 🤖 **AI 챗봇 (Router-Specialist 아키텍처)**:
  - **Router 노드**: 질문 유형 자동 분류 및 라우팅
  - **Specialist 에이전트**: 
    - `simple_chat`: 단순 대화, 날짜/시간 정보
    - `faq`: FAQ 벡터 검색 + 빗썸 고객지원 페이지 검색
    - `transaction`: 트랜잭션 해시 자동 감지 및 조회
    - `web_search`: Deep Research 워크플로우 (Planner → Researcher → Grader → Writer)
  - **실시간 스트리밍**: Server-Sent Events (SSE) 기반 토큰 스트리밍
  - **생각하는 과정 표시**: 검색 쿼리 및 결과를 사용자에게 시각화
- 📊 **대화 기록 관리**: MongoDB 기반 세션별 대화 저장
- 🐳 **Docker 기반 배포**: AWS EC2 배포 지원

## 프로젝트 구성

```
.
├── chatbot/                      # 챗봇 핵심 모듈
│   ├── __init__.py
│   ├── graph.py                  # LangGraph 워크플로우 (메인 구현)
│   ├── chatbot_graph.py         # 하위 호환성 래퍼
│   ├── configuration.py          # 설정 관리 (환경 변수, LLM 설정 등)
│   ├── models.py                 # 타입 정의 (ChatState, QuestionType 등)
│   ├── mongodb_client.py        # MongoDB Atlas 연결 및 대화 기록 관리
│   ├── vector_store.py          # MongoDB 벡터 검색 (FAQ 검색)
│   ├── utils.py                 # 유틸리티 함수 (에러 처리, 로깅 등)
│   ├── coingecko.py             # CoinGecko API 서비스 (과거 시세)
│   ├── coinmarketcap.py         # CoinMarketCap API 서비스 (현재 시세)
│   ├── exchange_rate.py         # 환율 정보 서비스
│   ├── nodes/                   # LangGraph 노드 구현
│   │   ├── __init__.py
│   │   ├── router.py            # 질문 분류 및 라우팅
│   │   ├── intent_clarifier.py  # 의도 명확화
│   │   ├── writer.py            # 최종 답변 작성
│   │   ├── save_response.py    # 응답 저장 (MongoDB)
│   │   ├── specialists/        # 전문가 에이전트
│   │   │   ├── __init__.py
│   │   │   ├── simple_chat.py   # 단순 대화 처리
│   │   │   ├── faq.py          # FAQ 검색 및 답변
│   │   │   └── transaction.py  # 트랜잭션 조회
│   │   └── deep_research/      # Deep Research 워크플로우
│   │       ├── __init__.py
│   │       ├── planner.py      # 검색 계획 수립
│   │       ├── researcher.py   # 웹 검색 수행
│   │       ├── grader.py       # 검색 결과 평가
│   │       ├── summarizer.py   # 검색 결과 요약
│   │       └── check_db.py     # DB 재검색
│   └── prompts/                # LLM 프롬프트 템플릿
│       ├── __init__.py
│       └── templates.py        # 프롬프트 템플릿 정의
├── src/                        # 트랜잭션 조회 서비스
│   └── services/
│       ├── __init__.py
│       ├── transaction_service.py  # 트랜잭션 감지 및 조회
│       ├── chain_configs.py        # 31개 체인 설정
│       └── cache.py               # 캐시 관리
├── templates/                  # HTML 템플릿
│   ├── chatbot.html            # 챗봇 UI (스트리밍 지원)
│   ├── explorer_ui.html        # 트랜잭션 조회 UI
│   └── ...                    # 기타 템플릿
├── scripts/                   # 유틸리티 스크립트
│   ├── data/                 # 데이터 관리
│   │   ├── import_faq.py    # FAQ 데이터 임포트
│   │   ├── setup_vector_db.py  # 벡터 DB 설정
│   │   ├── crawl_bithumb.py    # 빗썸 크롤링
│   │   └── check_similarity_score.py  # 유사도 점수 확인
│   └── deploy/              # 배포 스크립트
│       ├── before_install.sh
│       ├── after_install.sh
│       ├── start_application.sh
│       └── stop_application.sh
├── docs/                     # 문서
│   ├── docs.md              # 전체 개발 문서
│   ├── ROUTER_SPECIALIST_ARCHITECTURE.md
│   ├── STREAMING_IMPROVEMENTS.md
│   ├── DEBUG_MODE_GUIDE.md
│   └── ...                  # 기타 문서
├── docker/                   # Docker 설정
│   ├── Dockerfile.dev       # 개발용 Dockerfile
│   ├── Dockerfile.prod     # 프로덕션용 Dockerfile
│   └── entrypoint.sh       # Docker 진입점 스크립트
├── tests/                   # 테스트
│   ├── __init__.py
│   └── test_logging.py
├── main.py                  # FastAPI 애플리케이션 (메인 진입점)
├── requirements.txt         # Python 의존성
├── docker-compose.yml       # Docker Compose 설정
├── langgraph.json          # LangGraph CLI 설정
├── .env.example            # 환경 변수 예시 (선택사항)
└── README.md               # 이 파일
```

## 설치 방법

### 사전 요구사항

- **Python**: 3.12 이상
- **MongoDB Atlas**: 벡터 검색 인덱스 필요
- **OpenAI API 키**: 필수
- **Google Custom Search API 키**: 선택사항 (웹 검색용)
- **Docker & Docker Compose**: 선택사항 (컨테이너 배포용)

### 1. 저장소 복제

```bash
git clone https://github.com/aripos1/txidchatbot.git
cd txidchatbot
```

### 2. 가상 환경 생성 및 활성화

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

**또는 `uv` 사용:**
```bash
uv venv
source .venv/bin/activate  # Linux/Mac
# Windows: .venv\Scripts\activate
```

### 3. 의존성 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 변수들을 설정하세요:

#### 필수 환경 변수

```bash
# OpenAI API (필수)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# MongoDB Atlas (필수)
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGODB_DATABASE=chatbot_db
```

#### 선택적 환경 변수

```bash
# 검색 API 설정
SEARCH_API=google  # 또는 duckduckgo
GOOGLE_API_KEY=your_google_api_key  # Google Custom Search 사용 시
GOOGLE_CX=your_google_cx  # Google Custom Search 사용 시

# 벡터 검색 설정
SIMILARITY_THRESHOLD=0.7
VECTOR_SEARCH_LIMIT=3

# LLM 모델 설정 (각 노드별로 다른 모델 사용 가능)
PLANNER_MODEL=gpt-4o-mini
PLANNER_TEMPERATURE=0.3
WRITER_MODEL=gpt-4o-mini
WRITER_TEMPERATURE=0.7
SUMMARIZATION_MODEL=gpt-4o-mini
SUMMARIZATION_TEMPERATURE=0.3

# 검색 결과 제한
MAX_SEARCH_RESULTS=20
MAX_SEARCH_QUERIES=7
MAX_RESULTS_PER_QUERY=8

# 로깅
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

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
COINMARKETCAP_API_KEY=...  # 시세 조회용
```

자세한 환경 변수 목록은 `chatbot/configuration.py`를 참고하세요.

### 5. MongoDB Atlas 벡터 검색 인덱스 생성

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

### 6. FAQ 데이터 임포트 (선택사항)

```bash
python scripts/data/import_faq.py
```

## 사용법

### 로컬 개발 환경에서 실행

#### 옵션 1: FastAPI 직접 실행 (권장)

```bash
python main.py
```

서버가 `http://localhost:8000`에서 실행됩니다.

**접속 URL:**
- 챗봇 UI: `http://localhost:8000/chat`
- 트랜잭션 조회 UI: `http://localhost:8000/`
- 헬스 체크: `http://localhost:8000/health`

#### 옵션 2: Uvicorn으로 실행

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 옵션 3: LangGraph CLI 사용 (개발/디버깅용)

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

### API 사용 예시

#### 챗봇 스트리밍 API

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "오늘 비트코인 시세 알려줘",
    "session_id": "test_session_123"
  }'
```

#### 트랜잭션 조회 API

```bash
curl http://localhost:8000/api/tx/0x1234567890abcdef...
```

#### 대화 기록 조회

```bash
curl http://localhost:8000/api/chat/history/test_session_123
```

### 주요 기능 사용 예시

#### 1. 트랜잭션 조회

웹 UI에서 트랜잭션 해시를 입력하면 자동으로 31개 체인 중 적절한 체인을 감지하여 조회합니다.

**지원 체인:**
- Bitcoin 계열: Bitcoin, Litecoin, Dogecoin
- Ethereum 계열 (EVM): Ethereum, BNB Smart Chain, Polygon, Arbitrum, Optimism, Avalanche, Base, Mantle, Blast, Scroll, Linea, zkSync Era, World Chain, Swell L2, KAIA, Cronos, Sophon, WEMIX, Endurance, Ethereum Classic
- 기타: Tron, Solana, TON, Ripple, Stellar, Injective, Cosmos Hub, XPLA, Stacks

#### 2. 챗봇 질문 예시

- **FAQ 질문**: "원화 출금 방법 알려줘"
- **시세 질문**: "오늘 비트코인, 이더리움 시세 알려줘"
- **이벤트 질문**: "최근 진행중인 이벤트 알려줘"
- **트랜잭션 질문**: "0x1234... 트랜잭션 정보 알려줘"

## 버그 및 디버그

### 알려진 이슈

#### 1. 번호 리스트가 "1. 1. 1." 형식으로 표시되는 문제

**증상**: 딥리서치(이벤트 질문)에서 번호 리스트가 순차적으로 표시되지 않음

**원인**: LLM이 "1. 1. 1." 형식으로 출력하거나, 프론트엔드에서 번호 리스트를 제대로 감지하지 못함

**해결 방법**:
- 프론트엔드의 `formatMessage` 함수가 자동으로 "1. 2. 3." 형식으로 변환합니다
- 브라우저를 새로고침하면 정상적으로 표시됩니다
- 문제가 계속되면 브라우저 캐시를 삭제하세요

#### 2. 새로고침 시 메시지가 중복으로 표시되는 문제

**증상**: 페이지를 새로고침하면 대화 기록이 두 번씩 표시됨

**원인**: `loadChatHistory` 함수가 중복 호출되거나, 중복 메시지 체크가 제대로 작동하지 않음

**해결 방법**:
- `isHistoryLoaded` 플래그로 중복 로드 방지
- `Set`을 사용하여 같은 메시지는 한 번만 추가
- 이미 수정 완료 (v1.0.0)

#### 3. URL 인코딩 문제

**증상**: 빗썸 공식 홈페이지 링크가 `https://www.bithumb.xn--com)-ej5r32t/` 형식으로 잘못 표시됨

**원인**: LLM이 URL을 잘못 생성하거나 프론트엔드에서 잘못 처리

**해결 방법**:
- 프론트엔드에서 잘못된 퓨니코드 인코딩을 자동으로 수정
- 빗썸 URL은 자동으로 정규화됩니다 (`https://www.bithumb.com` 또는 `https://support.bithumb.com/hc/ko`)

#### 4. MongoDB 연결 실패

**증상**: "MongoDB 연결 실패" 오류

**해결 방법**:
- `.env` 파일의 `MONGODB_URI`가 올바른지 확인
- MongoDB Atlas에서 IP 화이트리스트 설정 확인
- 네트워크 연결 확인

#### 5. OpenAI API 오류

**증상**: "OpenAI API 키가 설정되지 않았습니다" 오류

**해결 방법**:
- `.env` 파일에 `OPENAI_API_KEY`가 올바르게 설정되었는지 확인
- API 키가 유효한지 확인
- API 사용량 한도 확인

#### 6. 벡터 검색 인덱스 오류

**증상**: FAQ 검색이 작동하지 않음

**해결 방법**:
- MongoDB Atlas에서 벡터 검색 인덱스가 생성되었는지 확인
- 인덱스 이름이 `vector_index`인지 확인
- 컬렉션 이름이 `knowledge_base`인지 확인

### 디버그 모드

#### 로그 레벨 설정

`.env` 파일에서 로그 레벨을 설정할 수 있습니다:

```bash
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

#### LangSmith 추적 활성화

디버깅을 위해 LangSmith 추적을 활성화할 수 있습니다:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=multi-chain-tx-lookup
```

LangSmith 대시보드에서 각 노드의 실행 과정을 시각화할 수 있습니다.

자세한 디버그 가이드는 [docs/DEBUG_MODE_GUIDE.md](docs/DEBUG_MODE_GUIDE.md)를 참고하세요.

## 참고 및 출처

### 주요 라이브러리

#### Core Framework
- **FastAPI** (>=0.104.1): 고성능 웹 프레임워크
- **Uvicorn** (>=0.24.0): ASGI 서버
- **Python-dotenv** (>=1.0.0): 환경 변수 관리

#### AI/ML
- **LangGraph** (>=1.0.0): 에이전트 워크플로우 관리
- **LangChain** (>=1.0.0): LLM 애플리케이션 프레임워크
- **LangChain OpenAI** (>=1.0.0): OpenAI 통합
- **LangChain Community** (>=0.4.1): 커뮤니티 통합
- **LangChain Core** (>=1.0.0): 핵심 기능
- **LangSmith** (>=0.1.0): 모니터링 및 디버깅
- **OpenAI** (>=1.54.0): OpenAI API 클라이언트

#### Database
- **PyMongo** (>=4.9,<4.10): MongoDB 드라이버
- **Motor** (==3.6.0): 비동기 MongoDB 드라이버

#### Web Scraping & Search
- **BeautifulSoup4** (>=4.12.3): HTML 파싱
- **LXML** (>=5.2.2): XML/HTML 파서
- **DDGS** (>=1.0.0): DuckDuckGo 검색 라이브러리
- **DuckDuckGo Search** (>=5.1.0): 구버전 호환성

#### Utilities
- **HTTPX** (>=0.25.1): 비동기 HTTP 클라이언트
- **Jinja2** (>=3.1.2): 템플릿 엔진
- **Pydantic** (>=2.0.0): 데이터 검증
- **NumPy** (>=1.26.4): 수치 계산

#### Deployment
- **Gunicorn** (>=21.2.0): WSGI 서버
- **Boto3** (>=1.34.11): AWS SDK
- **Sentry SDK** (>=1.39.1): 에러 추적

### 참고 문서

- [LangGraph 공식 문서](https://langchain-ai.github.io/langgraph/)
- [LangChain 공식 문서](https://python.langchain.com/)
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [MongoDB Atlas 벡터 검색 가이드](https://www.mongodb.com/docs/atlas/atlas-vector-search/)

### 프로젝트 문서

- [전체 개발 문서](docs/docs.md)
- [Router-Specialist 아키텍처](docs/ROUTER_SPECIALIST_ARCHITECTURE.md)
- [스트리밍 개선 사항](docs/STREAMING_IMPROVEMENTS.md)
- [LangGraph 1.0 업그레이드](docs/LANGGRAPH_1.0_REVIEW.md)
- [디버그 모드 가이드](docs/DEBUG_MODE_GUIDE.md)

## 업데이트 정보

### v1.0.0 (2025-01-03)

#### 주요 변경사항

- ✅ **Router-Specialist 아키텍처 구현**: 질문 유형별 전문가 에이전트 라우팅
- ✅ **31개 블록체인 네트워크 지원**: 주요 블록체인 트랜잭션 조회 기능
- ✅ **실시간 스트리밍**: Server-Sent Events (SSE) 기반 토큰 스트리밍
- ✅ **생각하는 과정 표시**: 검색 쿼리 및 결과를 사용자에게 시각화
- ✅ **Deep Research 워크플로우**: Planner → Researcher → Grader → Writer
- ✅ **MongoDB 벡터 검색**: FAQ 데이터베이스 검색
- ✅ **다중 코인 시세 조회**: 여러 코인을 한 번에 조회하는 기능
- ✅ **번호 리스트 자동 변환**: "1. 1. 1." → "1. 2. 3." 형식 자동 변환
- ✅ **URL 인코딩 수정**: 잘못된 URL 자동 수정
- ✅ **중복 메시지 방지**: 새로고침 시 메시지 중복 표시 방지

#### 버그 수정

- 🔧 번호 리스트가 "1. 1. 1." 형식으로 표시되는 문제 수정
- 🔧 새로고침 시 메시지가 중복으로 표시되는 문제 수정
- 🔧 URL 인코딩 문제 수정
- 🔧 스트리밍 중 번호 리스트 처리 개선

#### 제거된 기능

- ❌ `hybrid_specialist` 노드 제거 (중복 기능으로 인해 `faq_specialist`에서 직접 `planner`로 라우팅)

## 저작권

MIT License

Copyright (c) 2025 Multi-Chain Transaction Lookup & Bithumb Chatbot

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
