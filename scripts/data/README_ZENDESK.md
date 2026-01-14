# Zendesk API를 사용한 빗썸 FAQ 크롤링

이 스크립트는 Zendesk Help Center API를 사용하여 빗썸 고객지원 센터의 FAQ를 효율적으로 수집하고 MongoDB Atlas에 저장합니다.

## 장점

웹 크롤링 대비:
- ✅ **안정성**: API를 통한 구조화된 데이터 수집
- ✅ **효율성**: 페이지네이션을 통한 빠른 데이터 수집
- ✅ **완전성**: 모든 아티클을 빠짐없이 수집
- ✅ **메타데이터**: 카테고리, 섹션, 업데이트 날짜 등 풍부한 정보

## 설정

### 1. 기본 설정 (인증 없이)

공개 Help Center는 인증 없이도 접근 가능합니다. 다만 Rate Limit이 낮을 수 있습니다.

```bash
python scripts/data/crawl_bithumb.py
```

### 2. 인증 설정 (권장)

인증을 설정하면 Rate Limit이 더 높아져서 더 빠르게 데이터를 수집할 수 있습니다.

#### Zendesk API 토큰 생성

1. Zendesk 관리자 페이지에 로그인
2. **Admin** → **Apps and integrations** → **APIs** → **Zendesk API** 이동
3. **API token** 탭에서 새 토큰 생성
4. 토큰을 안전하게 저장

#### 환경 변수 설정

`.env` 파일에 다음을 추가:

```bash
# Zendesk API 인증 (선택사항)
ZENDESK_EMAIL=your-email@example.com
ZENDESK_API_TOKEN=your-api-token-here
```

## 사용 방법

### 수동 실행

```bash
python scripts/data/crawl_bithumb.py
```

### Airflow를 통한 자동 실행

Airflow DAG가 설정되어 있으면 매일 자동으로 실행됩니다.

```bash
cd airflow
docker-compose up -d
```

웹 UI (`http://localhost:8080`)에서 `bithumb_faq_crawler` DAG를 활성화하세요.

## 작동 방식

1. **Zendesk API 호출**: `/api/v2/help_center/ko/articles.json` 엔드포인트 사용
2. **페이지네이션**: 모든 페이지를 순회하며 아티클 수집
3. **텍스트 처리**: HTML 태그 제거 및 텍스트 정리
4. **청크 분할**: 긴 아티클을 1000자 단위로 분할 (200자 오버랩)
5. **임베딩 생성**: OpenAI Embedding API를 사용하여 벡터 생성
6. **MongoDB 저장**: 벡터와 메타데이터를 MongoDB Atlas에 저장

## Rate Limit

- **인증 없음**: 분당 약 200 요청
- **인증 있음**: 분당 약 700 요청

Rate Limit에 도달하면 자동으로 1분 대기 후 재시도합니다.

## 데이터 구조

각 아티클은 다음과 같은 메타데이터와 함께 저장됩니다:

```json
{
  "_id": "문서 ID",
  "text": "아티클 텍스트 (청크)",
  "source": "https://support.bithumb.com/hc/ko/articles/123456",
  "metadata": {
    "article_id": 123456,
    "title": "아티클 제목",
    "chunk_index": 0,
    "total_chunks": 3,
    "section_id": 123,
    "category_id": 456,
    "type": "zendesk_article",
    "updated_at": "2024-01-01T00:00:00Z",
    "created_at": "2024-01-01T00:00:00Z"
  },
  "embedding": [0.123, 0.456, ...],
  "created_at": "2024-01-01T00:00:00Z"
}
```

## 문제 해결

### Rate Limit 오류

인증을 설정하거나 요청 간 대기 시간을 늘리세요.

### API 접근 실패

1. Zendesk Help Center가 공개되어 있는지 확인
2. 네트워크 연결 확인
3. API 엔드포인트 URL 확인

### MongoDB 연결 실패

`.env` 파일의 `MONGODB_URI`가 올바른지 확인하세요.

## 참고 자료

- [Zendesk Help Center API 문서](https://developer.zendesk.com/api-reference/help_center/help-center-api/articles/)
- [Zendesk API 인증 가이드](https://support.zendesk.com/hc/en-us/articles/4408843597850)
