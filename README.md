# Multi-Chain Transaction Lookup & Bithumb Chatbot

블록체인 트랜잭션 조회 서비스와 빗썸 거래소 AI 챗봇을 통합한 웹 애플리케이션입니다.

## 주요 기능

- 🔍 **다양한 블록체인 네트워크 트랜잭션 조회**: Ethereum, BNB Smart Chain, Polygon 등
- 🤖 **AI 챗봇 (Open Deep Research 스타일)**:
  - FAQ 기반 자동 응답 (MongoDB Atlas 벡터 검색)
  - Deep Research 워크플로우 (4단계 LLM 역할 분리)
  - 최신 이벤트 및 공지사항 검색
- 📊 **대화 기록 관리**: MongoDB 기반 세션별 대화 저장
- 🐳 **Docker 기반 배포**: AWS EC2 배포 지원

## 빠른 시작

### 사전 요구사항

- Python 3.12 이상
- MongoDB Atlas 계정
- OpenAI API 키
- (선택) Google Custom Search API 키

### 로컬 개발 환경 설정

#### 1. 저장소 복제

```bash
git clone https://github.com/aripos1/txid.shop.git
cd txid.shop
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

# 블록체인 API 키들 (선택사항)
ETHEREUM_API_KEY=...
BNB_SMART_CHAIN_API_KEY=...
# ... 기타 체인 API 키들
```

자세한 환경 변수 목록은 [docs.md](docs.md)를 참고하세요.

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
python scripts/import_faq.py
```

#### 7. 서버 실행

**옵션 1: FastAPI 직접 실행 (현재 방식)**
```bash
python main.py
```
서버가 `http://localhost:8000`에서 실행됩니다.

**옵션 2: LangGraph CLI 사용 (Open Deep Research 방식)**
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
│   ├── chatbot_graph.py  # LangGraph 워크플로우
│   ├── configuration.py  # 설정 관리
│   ├── mongodb_client.py # MongoDB 연결
│   └── vector_store.py   # 벡터 검색
├── scripts/              # 유틸리티 스크립트
│   ├── import_faq.py     # FAQ 데이터 임포트
│   └── check_similarity_score.py  # 유사도 점수 확인
├── docs/                 # 문서
│   ├── AWS_LOG_GUIDE.md
│   ├── DEBUG_MODE_GUIDE.md
│   └── COMPARISON_WITH_OPEN_DEEP_RESEARCH.md
├── templates/            # HTML 템플릿
├── main.py              # FastAPI 애플리케이션
├── requirements.txt     # Python 의존성
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

### 대화 기록

- **GET /api/chat/history/{session_id}**: 대화 기록 조회
- **DELETE /api/chat/history/{session_id}**: 대화 기록 삭제

자세한 API 문서는 [docs.md](docs.md)를 참고하세요.

## 배포

### AWS EC2 배포

```bash
# 배포 스크립트 실행
./deploy.sh

# 또는 수동 배포
docker-compose build --no-cache
docker-compose up -d
```

자세한 배포 가이드는 [docs.md](docs.md)의 "7. 배포" 섹션을 참고하세요.

## 개발 문서

- [전체 개발 문서](docs.md)
- [AWS 로그 확인 가이드](docs/AWS_LOG_GUIDE.md)
- [디버그 모드 가이드](docs/DEBUG_MODE_GUIDE.md)
- [점수 확인 가이드](docs/SCORE_CHECK_GUIDE.md)
- [Open Deep Research 비교](docs/COMPARISON_WITH_OPEN_DEEP_RESEARCH.md)

## 기술 스택

- **Backend**: FastAPI, Python 3.12
- **AI/ML**: LangGraph, LangChain, OpenAI
- **Database**: MongoDB Atlas (Vector Search)
- **Containerization**: Docker, Docker Compose
- **Deployment**: AWS EC2

## 라이선스

이 프로젝트는 개인 프로젝트입니다.

## 기여

이슈 및 풀 리퀘스트를 환영합니다!

