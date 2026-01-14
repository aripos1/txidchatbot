# 이미지 처리 가이드

빗썸 FAQ 크롤링 시 이미지가 포함된 아티클을 어떻게 처리하는지 설명합니다.

## 🖼️ 이미지 처리 방식

### 1. 이미지 정보 추출

크롤링 시 다음 정보를 자동으로 추출합니다:

- **이미지 URL**: 이미지의 실제 주소
- **Alt 텍스트**: 이미지 대체 텍스트 (접근성용)
- **Title 속성**: 이미지 제목
- **캡션**: 이미지 아래 설명 텍스트
- **주변 텍스트**: 이미지 앞뒤 설명 텍스트

### 2. 이미지 설명을 텍스트로 변환

이미지의 설명 정보를 본문에 추가하여 **검색 가능하게** 만듭니다:

```
[이미지 설명: 로그인 화면]
[이미지 캡션: 1단계: 이메일 입력]
[이미지 주변 설명: 위 화면에서 이메일을 입력하세요]
```

이렇게 하면 사용자가 "로그인 화면" 또는 "이메일 입력"으로 검색해도 해당 아티클을 찾을 수 있습니다.

### 3. 메타데이터에 이미지 정보 저장

MongoDB에 저장될 때 이미지 정보가 메타데이터에 포함됩니다:

```json
{
  "_id": "문서ID",
  "text": "아티클 텍스트 청크",
  "source": "https://support.bithumb.com/hc/ko/articles/123456",
  "metadata": {
    "article_id": "123456",
    "title": "아티클 제목",
    "images": [
      {
        "url": "https://support.bithumb.com/image.png",
        "alt": "로그인 화면",
        "caption": "1단계: 이메일 입력",
        "context": "위 화면에서 이메일을 입력하세요"
      }
    ]
  }
}
```

## 📋 처리 예시

### 예시 1: Alt 텍스트가 있는 이미지

**HTML:**
```html
<img src="/images/login.png" alt="로그인 화면" />
<p>위 화면에서 이메일을 입력하세요.</p>
```

**추출된 정보:**
- URL: `https://support.bithumb.com/images/login.png`
- Alt: `로그인 화면`
- 주변 텍스트: `위 화면에서 이메일을 입력하세요.`

**본문에 추가되는 텍스트:**
```
[이미지 설명: 로그인 화면]
[이미지 주변 설명: 위 화면에서 이메일을 입력하세요.]
```

### 예시 2: 캡션이 있는 이미지

**HTML:**
```html
<figure>
  <img src="/images/step1.png" alt="1단계" />
  <figcaption>1단계: 이메일 입력</figcaption>
</figure>
```

**추출된 정보:**
- URL: `https://support.bithumb.com/images/step1.png`
- Alt: `1단계`
- 캡션: `1단계: 이메일 입력`

**본문에 추가되는 텍스트:**
```
[이미지 설명: 1단계]
[이미지 캡션: 1단계: 이메일 입력]
```

## 🔍 검색 가능성

이미지 설명이 텍스트로 변환되므로:

✅ **"로그인 화면"** 검색 → 이미지가 포함된 아티클 찾기 가능
✅ **"이메일 입력"** 검색 → 캡션이 있는 이미지 아티클 찾기 가능
✅ **"1단계"** 검색 → 단계별 이미지가 있는 가이드 찾기 가능

## 💾 저장 구조

### 이미지 정보 구조

```python
{
    "url": "https://support.bithumb.com/images/example.png",  # 이미지 URL
    "alt": "예시 이미지",  # Alt 텍스트 (있을 경우)
    "title": "이미지 제목",  # Title 속성 (있을 경우)
    "caption": "이미지 캡션",  # 캡션 (있을 경우)
    "context": "이미지 주변 설명"  # 주변 텍스트 (있을 경우)
}
```

### 메타데이터 저장

- **첫 번째 청크**에만 이미지 정보 저장 (중복 방지)
- 모든 이미지 정보를 배열로 저장
- 각 이미지의 URL, 설명 등을 포함

## 🎯 활용 방법

### 챗봇에서 이미지 정보 활용

검색 결과에 이미지가 포함된 경우:

```python
# 검색 결과에서 이미지 정보 추출
result = await vector_store.search("로그인 방법")
if result and result[0].get("metadata", {}).get("images"):
    images = result[0]["metadata"]["images"]
    # 이미지 URL을 사용자에게 제공
    for img in images:
        print(f"이미지: {img['url']}")
        if img.get('alt'):
            print(f"설명: {img['alt']}")
```

### 사용자에게 이미지 링크 제공

챗봇 응답에 이미지 링크를 포함할 수 있습니다:

```
로그인 방법은 다음과 같습니다:

1. 이메일 입력
   [이미지: https://support.bithumb.com/images/login.png]

2. 비밀번호 입력
   [이미지: https://support.bithumb.com/images/password.png]
```

## ⚙️ 설정

이미지 처리는 자동으로 수행됩니다. 추가 설정이 필요 없습니다.

### 이미지 추출 범위

- 본문(`article-body`) 내 이미지
- 메인 콘텐츠 영역 내 이미지
- 전체 페이지 이미지 (본문을 찾지 못한 경우)

### 제외되는 이미지

- 로고, 배너 등 네비게이션 이미지
- 광고 이미지
- 아이콘 (너무 작은 이미지)

## 📊 통계

크롤링 후 이미지 통계를 확인할 수 있습니다:

```python
# MongoDB에서 이미지가 포함된 아티클 수 확인
images_count = await collection.count_documents({
    "metadata.images": {"$exists": True, "$ne": []}
})
```

## 🔧 문제 해결

### 이미지가 추출되지 않는 경우

1. **HTML 구조 확인**: 이미지가 `<img>` 태그로 되어 있는지 확인
2. **상대 경로 문제**: 상대 경로는 자동으로 절대 경로로 변환됨
3. **Lazy Loading**: `data-src`, `data-lazy-src` 속성도 자동으로 처리됨

### 이미지 URL이 잘못된 경우

- 상대 경로(`/images/...`)는 자동으로 `https://support.bithumb.com/images/...`로 변환
- 프로토콜 없는 URL(`//example.com/...`)은 `https:`로 시작하도록 변환

## 📝 참고

- 이미지 파일 자체는 다운로드하지 않습니다 (URL만 저장)
- 이미지 설명만 텍스트로 변환하여 검색 가능하게 만듭니다
- 이미지가 많은 아티클의 경우 메타데이터 크기가 커질 수 있습니다
