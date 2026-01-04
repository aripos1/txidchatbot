"""
빗썸 고객지원 페이지 크롤링 및 벡터 DB 저장 스크립트
여러 FAQ 페이지를 한 번에 크롤링할 수 있습니다.
"""
import asyncio
from chatbot.vector_store import vector_store
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 빗썸 FAQ 페이지 URL 목록
BITHUMB_FAQ_URLS = [
    "https://www.bithumb.com/customer_support/info",  # 고객지원 안내
    "https://www.bithumb.com/customer_support/faq",    # FAQ 페이지
    # 추가 FAQ 페이지가 있다면 여기에 추가
    # "https://www.bithumb.com/customer_support/guide",  # 이용 가이드
    # "https://www.bithumb.com/customer_support/notice", # 공지사항
]

async def main():
    """메인 함수"""
    print("=" * 60)
    print("빗썸 고객지원 페이지 크롤링 및 벡터 DB 저장")
    print("=" * 60)
    
    # MongoDB 연결
    print("\n1. MongoDB Atlas 연결 중...")
    connected = await vector_store.connect()
    if not connected:
        print("❌ MongoDB 연결 실패. 연결 설정을 확인해주세요.")
        return
    
    print("✅ MongoDB 연결 성공!")
    
    # 크롤링할 URL 목록
    print(f"\n2. 크롤링할 페이지: {len(BITHUMB_FAQ_URLS)}개")
    for i, url in enumerate(BITHUMB_FAQ_URLS, 1):
        print(f"   {i}. {url}")
    
    print("\n3. 웹 페이지 크롤링 시작...")
    print("   (이 작업은 몇 분 걸릴 수 있습니다...)")
    print("-" * 60)
    
    success_count = 0
    fail_count = 0
    
    # 각 URL 크롤링 및 저장
    for i, url in enumerate(BITHUMB_FAQ_URLS, 1):
        try:
            print(f"\n[{i}/{len(BITHUMB_FAQ_URLS)}] 크롤링 중: {url}")
            await vector_store.crawl_and_store(url)
            success_count += 1
            print(f"✅ 완료: {url}")
        except Exception as e:
            fail_count += 1
            print(f"❌ 실패: {url} - {e}")
            continue
    
    print("\n" + "=" * 60)
    print(f"✅ 크롤링 완료!")
    print(f"   성공: {success_count}개")
    print(f"   실패: {fail_count}개")
    print("=" * 60)
    
    print("\n📌 다음 단계:")
    print("1. MongoDB Atlas에서 벡터 검색 인덱스가 생성되었는지 확인")
    print("2. FAQ Specialist에서 DB 검색을 활성화하면 더 정확한 답변 가능")
    print("3. 정기적으로 FAQ 페이지를 업데이트하여 최신 정보 유지")
    
    # 연결 해제
    await vector_store.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

