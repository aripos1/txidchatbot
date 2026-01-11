# Google AdSense 설정 가이드

## 승인 전 상태

현재 광고 영역은 **승인 전에는 표시되지 않습니다**. 이는 Google AdSense 정책상 문제가 없습니다.

### 승인 전
- ✅ 광고 영역이 화면에 표시되지 않음
- ✅ 레이아웃은 광고에 최적화되어 있음
- ✅ 실제 광고 코드는 삽입하지 않음

### 승인 후

Google AdSense 승인을 받은 후, 다음 단계를 따라주세요:

#### 1. 광고 코드 삽입

각 광고 영역에 실제 AdSense 광고 코드를 삽입하세요:

**예시:**
```html
<div class="adsense-container adsense-header-banner">
    <ins class="adsbygoogle"
         style="display:block"
         data-ad-client="ca-pub-5240424281235281"
         data-ad-slot="1234567890"
         data-ad-format="auto"
         data-full-width-responsive="true"></ins>
    <script>
         (adsbygoogle = window.adsbygoogle || []).push({});
    </script>
</div>
```

#### 2. 광고 슬롯 위치

광고 코드를 삽입할 위치:

1. **헤더 아래 배너** (`templates/explorer_ui.html` 라인 23-26, `templates/chatbot.html` 라인 139-141)
   - 크기: 728x90 (데스크톱)
   
2. **사이드바 상단** (`templates/explorer_ui.html` 라인 131-134, `templates/chatbot.html` 라인 203-206)
   - 크기: 300x250 또는 300x600

3. **사이드바 중간** (`templates/explorer_ui.html` 라인 137-140, `templates/chatbot.html` 라인 209-212)
   - 크기: 300x600

4. **콘텐츠 중간 배너** (`templates/explorer_ui.html` 라인 55-57, 99-101)
   - 크기: 728x90

5. **푸터 위 배너** (`templates/explorer_ui.html` 라인 163-165, `templates/chatbot.html` 라인 217-219)
   - 크기: 728x90

#### 3. 자동 표시

광고 코드를 삽입하면 자동으로 영역이 표시됩니다. JavaScript가 광고 코드(`<ins>`)를 감지하여 자동으로 처리합니다.

## 주의사항

- ✅ 승인 전에는 실제 광고 코드를 삽입하지 마세요
- ✅ 광고 코드 삽입 후에는 주석을 제거해도 됩니다
- ✅ 광고 정책을 준수하세요 (클릭 유도 금지 등)
- ✅ 반응형 광고를 사용하면 다양한 화면 크기에 자동으로 대응됩니다
