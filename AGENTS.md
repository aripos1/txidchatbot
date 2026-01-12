# AI 컨텍스트 및 거버넌스 시스템

## Project Context & Operations

### 비즈니스 목표

Multi-Chain Transaction Lookup & Bithumb Chatbot은 블록체인 트랜잭션 조회 서비스와 빗썸 거래소 AI 챗봇을 통합한 웹 애플리케이션입니다. 주요 기능:

- 31개 블록체인 네트워크 트랜잭션 조회 (Bitcoin, Ethereum, BNB Smart Chain, Polygon, Solana, Tron 등)
- Router-Specialist 아키텍처 기반 AI 챗봇 (FAQ 검색, 트랜잭션 조회, 웹 검색, 시세 조회)
- 실시간 스트리밍 응답 (Server-Sent Events)
- MongoDB 벡터 검색 기반 FAQ 시스템

### Tech Stack

- **Backend Framework**: FastAPI 0.104.1+
- **ASGI Server**: Uvicorn 0.24.0+
- **AI Framework**: LangGraph 1.0+, LangChain 1.0+
- **Database**: MongoDB Atlas (벡터 검색 지원)
- **LLM Provider**: OpenAI (GPT-4o-mini)
- **Template Engine**: Jinja2 3.2+
- **HTTP Client**: HTTPX 0.25.1+

### Operational Commands

**개발 환경 실행:**
```bash
python main.py
```

**프로덕션 환경 실행:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Docker Compose 실행:**
```bash
docker-compose up -d
```

**의존성 설치:**
```bash
pip install -r requirements.txt
```

**환경 변수 설정:**
`.env` 파일을 생성하고 필수 환경 변수를 설정하세요. 자세한 내용은 `README.md`의 "환경 변수 설정" 섹션을 참고하세요.

**테스트 실행:**
```bash
python -m pytest tests/
```

## Golden Rules

### Immutable (절대 타협 불가)

1. **API 키 보안**: 절대 코드에 API 키를 하드코딩하지 마세요. 모든 API 키는 환경 변수로 관리하세요.
2. **MongoDB 연결**: MongoDB 연결 실패 시에도 서버는 계속 실행되어야 합니다 (비동기 연결, 타임아웃 처리).
3. **LangGraph 버전**: LangGraph 1.0+ API를 사용해야 합니다. 구버전 API는 사용하지 마세요.
4. **프롬프트 규칙**: `chatbot/prompts/templates.py`의 프롬프트 규칙을 절대 위반하지 마세요. JSON 구조를 응답에 포함하지 마세요.
5. **스트리밍 응답**: LLM 응답의 JSON 구조는 스트리밍에서 자동으로 필터링되어야 합니다.

### Do's & Don'ts

**Do's:**

- 항상 공식 SDK/Library를 사용하세요 (LangGraph, LangChain, FastAPI, MongoDB).
- 환경 변수는 `chatbot/configuration.py`에서 중앙 관리하세요.
- 에러 발생 시 로깅을 적절히 수행하고, 사용자에게 친절한 오류 메시지를 제공하세요.
- 새로운 노드를 추가할 때는 `chatbot/nodes/` 디렉토리의 기존 패턴을 따르세요.
- 프롬프트 수정 시 `chatbot/prompts/templates.py`를 업데이트하세요.
- 트랜잭션 서비스 수정 시 `src/services/transaction_service.py`와 `src/services/chain_configs.py`를 함께 검토하세요.

**Don'ts:**

- API 키를 코드에 직접 작성하지 마세요.
- MongoDB 연결이 없어도 서버가 크래시되지 않도록 하세요.
- LangGraph 구버전 API를 사용하지 마세요.
- 프롬프트에 JSON 구조, 검색 쿼리, 연구 계획 등 내부 처리 정보를 포함하지 마세요.
- LLM 응답에 JSON 형식(중괄호로 시작하는 구조)을 사용하지 마세요.
- 번호 매기기를 중복하여 사용하지 마세요 (1. 2. 3. 형식 유지).
- URL 링크에 마크다운 형식이나 잘못된 인코딩을 사용하지 마세요.

## Standards & References

### 코딩 컨벤션

- **Python 스타일**: PEP 8 준수
- **타입 힌팅**: 가능한 모든 함수에 타입 힌팅 추가
- **문서화**: 모든 공개 함수/클래스에 docstring 추가
- **비동기 처리**: I/O 작업은 반드시 `async/await` 사용
- **로깅**: `logging` 모듈 사용, 환경 변수 `LOG_LEVEL`로 제어

### Git 전략

- **커밋 메시지**: 한국어 또는 영어, 간결하게 작성
- **브랜치 전략**: `main` 브랜치에 직접 커밋 가능, 큰 기능은 별도 브랜치에서 개발 후 머지
- **코드 리뷰**: 프로덕션 배포 전 코드 검토 권장

### Maintenance Policy

규칙과 코드의 괴리가 발생하면 즉시 업데이트를 제안하세요. `AGENTS.md` 파일은 프로젝트의 "살아있는 문서"입니다.

## Context Map (Action-Based Routing)

다음 디렉토리에서 작업할 때는 해당 `AGENTS.md` 파일을 먼저 참고하세요:

- **[챗봇 그래프 수정 (LangGraph)](./chatbot/AGENTS.md)** — LangGraph 노드 추가/수정, 워크플로우 변경 시.
- **[트랜잭션 서비스 수정](./src/services/AGENTS.md)** — 멀티체인 트랜잭션 조회 로직 추가/수정 시.
- **[프론트엔드 템플릿 수정](./templates/AGENTS.md)** — Jinja2 HTML 템플릿, 챗봇 UI 스타일링 시.
- **[프롬프트 수정](./chatbot/prompts/AGENTS.md)** — LLM 프롬프트 템플릿 수정 시.
