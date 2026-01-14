# Selenium 설정 가이드

403 Forbidden 오류를 해결하기 위해 Selenium을 사용하는 방법입니다.

## 설치 방법

### 1. Selenium 설치

```bash
pip install selenium
```

### 2. ChromeDriver 설치

#### Windows:
1. Chrome 버전 확인: Chrome 브라우저 → 설정 → Chrome 정보
2. ChromeDriver 다운로드: https://chromedriver.chromium.org/downloads
3. 다운로드한 `chromedriver.exe`를 PATH에 추가하거나 프로젝트 폴더에 저장

#### 자동 설치 (권장):
```bash
pip install webdriver-manager
```

그리고 코드에서:
```python
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)
```

## 사용 방법

### 기본 사용 (헤드리스 모드)

```bash
python scripts/data/crawl_bithumb_selenium.py --limit 3
```

### 브라우저 표시 (디버깅용)

```bash
python scripts/data/crawl_bithumb_selenium.py --limit 3 --no-headless
```

## 장점

- ✅ Cloudflare 보호 우회 가능
- ✅ JavaScript 렌더링 지원
- ✅ 실제 브라우저처럼 동작
- ✅ 쿠키/세션 자동 관리

## 단점

- ❌ 느림 (브라우저 실행 시간)
- ❌ 리소스 사용량 많음
- ❌ ChromeDriver 설치 필요

## 문제 해결

### ChromeDriver를 찾을 수 없음

**해결:**
1. ChromeDriver를 PATH에 추가
2. 또는 `webdriver-manager` 사용

### 브라우저가 시작되지 않음

**해결:**
1. Chrome 브라우저가 설치되어 있는지 확인
2. ChromeDriver 버전이 Chrome 버전과 일치하는지 확인

### 여전히 403 오류

**해결:**
1. `--no-headless` 옵션으로 브라우저를 표시하여 수동 확인
2. Cloudflare 체크를 수동으로 통과
3. 또는 Playwright 사용 고려 (더 현대적)

## Playwright 대안

Selenium 대신 Playwright를 사용할 수도 있습니다:

```bash
pip install playwright
playwright install chromium
```

Playwright가 더 빠르고 현대적입니다.
