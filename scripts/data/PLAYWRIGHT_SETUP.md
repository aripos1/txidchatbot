# Playwright 설정 가이드

403 Forbidden 오류를 해결하기 위해 Playwright를 사용하는 방법입니다.

## 설치 방법

### 1. Playwright 설치

```bash
pip install playwright
```

### 2. 브라우저 설치

```bash
playwright install chromium
```

또는 모든 브라우저 설치:
```bash
playwright install
```

## 사용 방법

### 기본 테스트 (3개 아티클, 헤드리스 모드)

```bash
python scripts/data/test_crawl_playwright.py --limit 3
```

### 브라우저 표시 (디버깅용)

```bash
python scripts/data/test_crawl_playwright.py --limit 3 --no-headless
```

### 전체 크롤링

```bash
python scripts/data/crawl_bithumb_playwright.py
```

### 제한된 크롤링

```bash
python scripts/data/crawl_bithumb_playwright.py --limit 10
```

## Playwright의 장점

- ✅ **빠름**: Selenium보다 2-3배 빠름
- ✅ **안정적**: 더 나은 에러 처리
- ✅ **Cloudflare 우회**: 실제 브라우저처럼 동작
- ✅ **JavaScript 지원**: 완전한 JavaScript 렌더링
- ✅ **자동 대기**: 네트워크 유휴 상태까지 자동 대기
- ✅ **설치 간편**: 브라우저 자동 다운로드

## Selenium vs Playwright

| 기능 | Selenium | Playwright |
|------|----------|------------|
| 속도 | 느림 | 빠름 (2-3배) |
| 안정성 | 보통 | 높음 |
| 설치 | ChromeDriver 필요 | 자동 설치 |
| JavaScript | 지원 | 완벽 지원 |
| Cloudflare | 우회 가능 | 우회 가능 |

## 문제 해결

### Playwright를 찾을 수 없음

**해결:**
```bash
pip install playwright
playwright install chromium
```

### 브라우저가 시작되지 않음

**해결:**
1. 브라우저가 제대로 설치되었는지 확인:
   ```bash
   playwright install chromium --force
   ```

2. 시스템 권한 확인 (Linux/Mac):
   ```bash
   sudo playwright install chromium
   ```

### 여전히 403 오류

**해결:**
1. `--no-headless` 옵션으로 브라우저를 표시하여 수동 확인
2. Cloudflare 체크를 수동으로 통과
3. 더 긴 대기 시간 설정 (코드에서 `await asyncio.sleep(3)` 등)

### 메모리 부족

**해결:**
- 헤드리스 모드 사용 (기본값)
- 한 번에 처리하는 아티클 수 제한 (`--limit`)

## 성능 최적화

### 병렬 처리 (고급)

여러 페이지를 동시에 처리하려면:

```python
async def process_multiple_articles(pages: List[Page], urls: List[str]):
    tasks = []
    for page, url in zip(pages, urls):
        tasks.append(extract_article_content_playwright(page, url))
    return await asyncio.gather(*tasks)
```

## Airflow와 통합

Airflow DAG에서 Playwright를 사용하려면:

```python
# airflow/dags/bithumb_faq_crawler.py
def run_crawl_bithumb_faq():
    from scripts.data.crawl_bithumb_playwright import main
    import asyncio
    asyncio.run(main())
```

주의: Airflow 컨테이너에 Playwright 브라우저가 설치되어 있어야 합니다.

## 참고

- [Playwright 공식 문서](https://playwright.dev/python/)
- [Playwright Python API](https://playwright.dev/python/docs/api/class-playwright)
