# 프론트엔드 템플릿 모듈 컨텍스트

## Module Context

이 모듈은 Jinja2 기반 HTML 템플릿을 관리합니다.

**주요 컴포넌트:**

- **챗봇 UI**: `chatbot.html` - 실시간 스트리밍 챗봇 인터페이스
- **트랜잭션 조회 UI**: `explorer_ui.html` - 멀티체인 트랜잭션 조회 인터페이스
- **기타 페이지**: 빗썸 가이드, 컴플라이언스, 개인정보처리방침, 이용약관 등

**의존성 관계:**

- 모든 템플릿 → `base.html` (기본 레이아웃)
- `main.py` → Jinja2 템플릿 엔진 (템플릿 렌더링)
- 챗봇 UI → Server-Sent Events (실시간 스트리밍)

## Tech Stack & Constraints

### 필수 라이브러리

- **Jinja2**: 3.2+ (템플릿 엔진, FastAPI에서 자동 제공)

### 아키텍처 제약

1. **템플릿 상속**: 가능한 `base.html`을 상속하여 일관된 레이아웃 유지.
2. **정적 파일**: CSS/JS는 `static/` 디렉토리에 위치, 템플릿에서 `/static/` 경로로 참조.
3. **실시간 스트리밍**: 챗봇 UI는 Server-Sent Events (SSE) 사용.

### 사용 제한

- **절대 사용 금지**: 다른 템플릿 엔진 사용 (Jinja2만 사용).
- **권장하지 않음**: 인라인 스타일/스크립트 과다 사용 (별도 파일 권장).

## Implementation Patterns

### 새 템플릿 추가 패턴

**1. 기본 템플릿 상속:**

```jinja2
{% extends "base.html" %}

{% block title %}페이지 제목{% endblock %}

{% block content %}
<div class="container">
    <!-- 페이지 내용 -->
</div>
{% endblock %}
```

**2. `main.py`에 라우트 추가:**

```python
@app.get("/new-page", response_class=HTMLResponse)
async def new_page(request: Request):
    return templates.TemplateResponse("new_page.html", {"request": request})
```

### 챗봇 UI 스트리밍 패턴

**Server-Sent Events (SSE) 사용:**

```javascript
const eventSource = new EventSource('/api/chat/stream');

eventSource.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'token') {
        // 토큰 스트리밍 처리
        appendToken(data.content);
    } else if (data.type === 'done') {
        // 완료 처리
        eventSource.close();
    }
});
```

### 정적 파일 참조 패턴

**템플릿에서 정적 파일 참조:**

```jinja2
<link rel="stylesheet" href="/static/css/style.css">
<script src="/static/js/app.js"></script>
```

**`main.py`에서 정적 파일 마운트:**

```python
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")
```

## Testing Strategy

**테스트 명령어:**

브라우저에서 직접 테스트:

```bash
# 서버 실행
python main.py

# 브라우저에서 접속
# http://localhost:8000/chat (챗봇 UI)
# http://localhost:8000/ (트랜잭션 조회 UI)
```

**테스트 포인트:**

- 템플릿 렌더링 확인 (Jinja2 문법 오류).
- 정적 파일 로딩 확인 (CSS/JS).
- 챗봇 스트리밍 동작 확인 (SSE).
- 반응형 디자인 확인 (모바일/데스크톱).

## Local Golden Rules

### 이 모듈에서 범하기 쉬운 실수

**1. 템플릿 경로 오류:**

- **잘못된 예**: `templates/chatbot.html` 경로로 직접 참조
- **올바른 예**: `chatbot.html` (Jinja2가 `templates/` 디렉토리 기준)

**2. 정적 파일 경로 오류:**

- **잘못된 예**: `/static/css/style.css` 경로를 템플릿에 직접 작성
- **올바른 예**: `{{ url_for('static', path='css/style.css') }}` (Jinja2 URL 생성)

**3. SSE 연결 관리 오류:**

- **잘못된 예**: SSE 연결을 닫지 않음 → 메모리 누수
- **올바른 예**: 완료 시 `eventSource.close()` 호출

**4. XSS 보안 취약점:**

- **잘못된 예**: 사용자 입력을 그대로 렌더링 (`{{ user_input }}`)
- **올바른 예**: Jinja2 자동 이스케이핑 사용 또는 `| safe` 필터 사용 (신뢰할 수 있는 경우만)

**5. 템플릿 상속 누락:**

- **잘못된 예**: 모든 템플릿이 독립적인 HTML 구조
- **올바른 예**: `base.html` 상속하여 일관된 레이아웃 유지

### 권장 사항

- 새 템플릿 추가 시 `base.html`을 상속하세요.
- 정적 파일은 `static/` 디렉토리에 배치하세요.
- 챗봇 UI 수정 시 스트리밍 동작을 확인하세요.
- 템플릿 문법 오류는 서버 시작 시 자동 감지됩니다.
- XSS 공격 방지를 위해 사용자 입력은 자동 이스케이핑을 사용하세요.
