# 크롤링 테스트 가이드

빗썸 FAQ 크롤링이 제대로 작동하는지 테스트하는 방법입니다.

## 🧪 빠른 테스트

### 기본 테스트 (3개 아티클)

```bash
python scripts/data/test_crawl.py
```

또는

```bash
python scripts/data/test_crawl.py --limit 3
```

### 더 많은 아티클 테스트

```bash
# 5개 아티클 테스트
python scripts/data/test_crawl.py --limit 5

# 10개 아티클 테스트
python scripts/data/test_crawl.py --limit 10
```

## 📋 테스트 내용

테스트 스크립트는 다음을 확인합니다:

1. ✅ **MongoDB 연결**: MongoDB Atlas 연결 성공 여부
2. ✅ **아티클 발견**: 카테고리 → 섹션 → 아티클 탐색
3. ✅ **내용 추출**: 제목, 본문, 이미지 정보 추출
4. ✅ **벡터 DB 저장**: 임베딩 생성 및 MongoDB 저장

## 📊 테스트 결과 확인

### 성공 시 출력 예시

```
============================================================
빗썸 FAQ 크롤링 테스트
============================================================

1. MongoDB Atlas 연결 중...
✅ MongoDB 연결 성공!

2. 아티클 URL 발견 중... (최대 3개만 테스트)
------------------------------------------------------------
발견된 카테고리 수: 5
발견된 섹션 수: 12
총 발견된 아티클 수: 45

3. 테스트 대상: 3개 아티클 (전체 45개 중)
   1. https://support.bithumb.com/hc/ko/articles/123456
   2. https://support.bithumb.com/hc/ko/articles/123457
   3. https://support.bithumb.com/hc/ko/articles/123458

4. 크롤링 테스트 시작...
------------------------------------------------------------

[1/3] 크롤링 중: https://support.bithumb.com/hc/ko/articles/123456
   제목: 로그인 방법 안내...
   본문 길이: 1234자
   이미지 수: 2개
   이미지 정보:
     1. https://support.bithumb.com/images/login.png... (alt: 로그인 화면)
     2. https://support.bithumb.com/images/password.png... (alt: 비밀번호 입력)
   벡터 DB 저장 중...
✅ 저장 완료: 로그인 방법 안내...

[2/3] 크롤링 중: ...
...

============================================================
✅ 테스트 완료!
   성공: 3개
   실패: 0개
============================================================

✅ 크롤링이 정상적으로 작동합니다!

📊 테스트 결과:
   - 발견된 전체 아티클: 45개
   - 테스트한 아티클: 3개
   - 성공적으로 저장: 3개

💡 전체 크롤링을 실행하려면:
   python scripts/data/crawl_bithumb.py
```

## 🔍 문제 해결

### MongoDB 연결 실패

**증상:**
```
❌ MongoDB 연결 실패. 연결 설정을 확인해주세요.
```

**해결 방법:**
1. `.env` 파일에 `MONGODB_URI`가 설정되어 있는지 확인
2. MongoDB Atlas 네트워크 접근 설정 확인 (IP 화이트리스트)
3. 연결 문자열 형식 확인:
   ```
   MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
   ```

### 아티클 발견 실패

**증상:**
```
❌ 아티클을 찾을 수 없습니다.
```

**해결 방법:**
1. 인터넷 연결 확인
2. 빗썸 웹사이트 접근 가능 여부 확인
3. URL이 변경되었는지 확인: `https://support.bithumb.com/hc/ko`

### 내용 추출 실패

**증상:**
```
⚠️ 내용 추출 실패
⚠️ 본문이 비어있음
```

**해결 방법:**
1. 웹사이트 구조가 변경되었을 수 있음
2. 로그를 확인하여 상세 오류 메시지 확인
3. 해당 URL을 브라우저에서 직접 확인

### 저장 실패

**증상:**
```
⚠️ 저장 실패
```

**해결 방법:**
1. MongoDB 연결 상태 확인
2. OpenAI API 키가 설정되어 있는지 확인 (임베딩 생성 필요)
3. `.env` 파일 확인:
   ```
   OPENAI_API_KEY=your_api_key_here
   OPENAI_EMBEDDING_MODEL=text-embedding-3-small
   ```

## 📝 테스트 후 확인 사항

### MongoDB에서 데이터 확인

MongoDB Atlas에서 다음을 확인하세요:

1. **컬렉션 확인**: `knowledge_base` 컬렉션에 데이터가 있는지
2. **문서 수 확인**: 테스트한 아티클 수만큼 문서가 있는지
3. **임베딩 확인**: `embedding` 필드가 있는지
4. **이미지 정보 확인**: `metadata.images` 필드가 있는지

### 챗봇에서 검색 테스트

테스트 후 챗봇에서 검색이 잘 되는지 확인:

```python
# Python에서 직접 테스트
from chatbot.vector_store import vector_store
import asyncio

async def test_search():
    await vector_store.connect()
    results = await vector_store.search("로그인 방법", limit=3)
    for result in results:
        print(f"제목: {result.get('metadata', {}).get('title')}")
        print(f"점수: {result.get('score', 0):.4f}")
        print(f"텍스트: {result.get('text', '')[:100]}...")
        print()

asyncio.run(test_search())
```

## 🚀 전체 크롤링 실행

테스트가 성공하면 전체 크롤링을 실행할 수 있습니다:

```bash
python scripts/data/crawl_bithumb.py
```

또는 Airflow를 통해 자동 실행:

```bash
cd airflow
docker-compose up -d
# 웹 UI에서 DAG 활성화
```

## 💡 팁

- **처음 테스트**: `--limit 1`로 1개만 테스트하여 빠르게 확인
- **기능 확인**: `--limit 5`로 여러 기능(이미지, 텍스트 등) 확인
- **성능 테스트**: `--limit 10`으로 성능 확인

## 📞 문제가 계속되면

1. 로그 파일 확인
2. MongoDB Atlas 로그 확인
3. 네트워크 연결 확인
4. 환경 변수 설정 확인
