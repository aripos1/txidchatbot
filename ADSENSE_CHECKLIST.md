# Google AdSense 승인 체크리스트

## ✅ 완료된 항목

### 1. 기술적 요구사항
- [x] **AdSense 메타 태그 추가**: 모든 HTML 템플릿에 추가 완료
  - `templates/explorer_ui.html`
  - `templates/chatbot.html`
  - `templates/staking_calculator.html`
  - `templates/compliance.html`
  - `templates/bithumb_test.html`
  - `templates/bithumb_guide.html`
  - `templates/bithumb_mindmap.html`
  - `templates/privacy_policy.html`
  - `templates/terms_of_service.html`

- [x] **AdSense 스크립트 추가**: 모든 페이지에 자동 광고 스크립트 추가
- [x] **robots.txt 파일**: `/robots.txt` 생성 완료
- [x] **sitemap.xml 파일**: `/sitemap.xml` 생성 완료
- [x] **HTTPS 사용**: 필수 (배포 환경에서 확인 필요)

### 2. 법적 페이지
- [x] **Privacy Policy (개인정보처리방침)**: `/privacy-policy` 생성 완료
- [x] **Terms of Service (이용약관)**: `/terms-of-service` 생성 완료
- [x] **Google AdSense 정책 준수 내용 포함**: 두 페이지 모두 포함

### 3. SEO 최적화
- [x] **메타 설명(description) 태그**: 모든 페이지에 추가
- [x] **키워드(keywords) 태그**: 모든 페이지에 추가
- [x] **Open Graph 태그**: 소셜 미디어 공유용 태그 추가
- [x] **언어 설정**: `lang="ko"` 설정 완료
- [x] **모바일 친화적**: 반응형 디자인 구현 완료

### 4. 라우트 설정
- [x] **Privacy Policy 라우트**: `/privacy-policy` 추가 완료
- [x] **Terms of Service 라우트**: `/terms-of-service` 추가 완료
- [x] **robots.txt 라우트**: `/robots.txt` 추가 완료
- [x] **sitemap.xml 라우트**: `/sitemap.xml` 추가 완료

## ⚠️ 추가 작업 필요

### 1. Footer 링크 추가 (필수)
모든 페이지 하단에 Privacy Policy와 Terms of Service 링크를 추가해야 합니다.

**현재 상태**: Footer가 base.html에만 있음 (실제 사용되지 않는 템플릿)

**필요한 작업**:
- [ ] 각 템플릿 파일 하단에 Footer 추가
- [ ] 또는 공통 Footer 컴포넌트 생성 및 포함

**예시**:
```html
<footer style="...">
    <a href="/privacy-policy">개인정보처리방침</a>
    <a href="/terms-of-service">이용약관</a>
</footer>
```

### 2. Google Search Console 등록 (권장)
- [ ] [Google Search Console](https://search.google.com/search-console) 접속
- [ ] 사이트 추가: `https://txid.shop`
- [ ] 소유권 확인
- [ ] sitemap.xml 제출: `https://txid.shop/sitemap.xml`

### 3. 콘텐츠 확인 (중요)
- [ ] **최소 페이지 수**: 10개 이상의 고유한 콘텐츠 페이지 확인
  - 현재 페이지:
    - `/` (메인)
    - `/chat` (챗봇)
    - `/stk` (스테이킹 계산기)
    - `/compliance` (입출금 가이드)
    - `/bithumb-guide` (빗썸 API 가이드)
    - `/bithumb-test` (빗썸 테스트 - robots.txt에서 제외됨)
    - `/privacy-policy` (개인정보처리방침)
    - `/terms-of-service` (이용약관)
  - **총 8개 페이지** (bithumb-test 제외 시 7개)
  - **추가 콘텐츠 페이지 권장** (최소 2-3개)

- [ ] **각 페이지 콘텐츠 길이**: 최소 300-500 단어 권장
  - Privacy Policy: ✅ 충분함
  - Terms of Service: ✅ 충분함
  - 기타 페이지: 확인 필요

### 4. 트래픽 확인 (중요)
- [ ] **일일 방문자 수**: AdSense 승인에는 적절한 트래픽이 필요
- [ ] **유기적 트래픽**: 검색 엔진을 통한 자연스러운 방문자 필요

### 5. 사이트 품질 확인
- [ ] **로딩 속도**: 페이지 로드 시간 최적화
- [ ] **모바일 사용성**: 모바일에서 정상 작동 확인
- [ ] **브라우저 호환성**: 주요 브라우저에서 테스트
- [ ] **오류 없음**: 404 오류, 브로큰 링크 확인

## 📋 AdSense 승인 신청 체크리스트

### 사전 확인
- [ ] 모든 필수 페이지 생성 완료
- [ ] Footer에 Privacy Policy/Terms 링크 추가
- [ ] 사이트가 안정적으로 작동 (24/7)
- [ ] HTTPS 사용 확인
- [ ] robots.txt 및 sitemap.xml 접근 가능 확인
- [ ] 각 페이지에 충분한 콘텐츠 확인
- [ ] 최소 10개 이상의 고유한 페이지 확인

### 신청 절차
1. [Google AdSense](https://www.google.com/adsense) 방문
2. Google 계정으로 로그인
3. "시작하기" 클릭
4. 사이트 추가: `https://txid.shop`
5. AdSense 계정 ID 확인: `ca-pub-5240424281235281` (이미 설정됨)
6. 사이트 검증 완료 대기
7. 정책 준수 확인 대기
8. 승인 대기 (1-14일)

## 🚨 승인 거부 시 확인 사항

승인이 거부된 경우 다음을 확인하세요:

1. **콘텐츠 부족**
   - [ ] 페이지 수가 10개 이상인지 확인
   - [ ] 각 페이지에 충분한 콘텐츠(300-500 단어)가 있는지 확인

2. **트래픽 부족**
   - [ ] Google Analytics로 트래픽 확인
   - [ ] 일일 방문자 수가 충분한지 확인

3. **기술적 문제**
   - [ ] 사이트 접근 가능 여부 확인
   - [ ] HTTPS 정상 작동 확인
   - [ ] 모바일에서 정상 작동 확인

4. **정책 위반**
   - [ ] 저작권 침해 콘텐츠 없음 확인
   - [ ] 부적절한 콘텐츠 없음 확인
   - [ ] 모든 법적 페이지 존재 확인

## 📝 참고 문서

- [AdSense 설정 가이드](./docs/ADSENSE_SETUP_GUIDE.md)
- [Google AdSense 도움말](https://support.google.com/adsense)
- [AdSense 정책](https://support.google.com/adsense/answer/48182)

## ✅ 최종 확인

모든 항목이 완료되면 다음을 확인하세요:

1. [ ] `https://txid.shop/privacy-policy` 접속 가능
2. [ ] `https://txid.shop/terms-of-service` 접속 가능
3. [ ] `https://txid.shop/robots.txt` 접속 가능
4. [ ] `https://txid.shop/sitemap.xml` 접속 가능
5. [ ] 모든 페이지 하단에 Footer 링크 표시 확인
6. [ ] 페이지 소스에서 AdSense 메타 태그 확인
7. [ ] Google Search Console 등록 완료
8. [ ] 사이트가 안정적으로 작동 확인

---

**마지막 업데이트**: 2024-01-01

