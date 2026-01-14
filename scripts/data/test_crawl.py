"""
빗썸 FAQ 크롤링 테스트 스크립트
소수의 아티클만 크롤링하여 기능을 테스트합니다.
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.data.crawl_bithumb import (
    vector_store,
    discover_all_articles,
    extract_article_content,
    store_article_to_vector_db,
    BASE_URL,
    HELP_CENTER_BASE
)
import httpx
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def test_crawl(limit: int = 3):
    """크롤링 테스트 (소수의 아티클만)"""
    print("=" * 60)
    print("빗썸 FAQ 크롤링 테스트")
    print("=" * 60)
    
    # MongoDB 연결
    print("\n1. MongoDB Atlas 연결 중...")
    connected = await vector_store.connect()
    if not connected:
        print("❌ MongoDB 연결 실패. 연결 설정을 확인해주세요.")
        print("\n💡 확인 사항:")
        print("   - .env 파일에 MONGODB_URI가 설정되어 있는지 확인")
        print("   - MongoDB Atlas 네트워크 접근 설정 확인")
        return False
    
    print("✅ MongoDB 연결 성공!")
    
    # 아티클 URL 발견 (테스트용으로 소수만)
    print(f"\n2. 아티클 URL 발견 중... (최대 {limit}개만 테스트)")
    print("-" * 60)
    
    # 쿠키와 세션을 유지하기 위한 클라이언트 설정
    async with httpx.AsyncClient(
        timeout=30.0, 
        follow_redirects=True,
        cookies={},
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    ) as client:
        # 먼저 메인 페이지에 접속하여 쿠키 받기
        try:
            logging.info("메인 페이지 접속하여 쿠키 받는 중...")
            from scripts.data.crawl_bithumb import BASE_URL, HEADERS
            await client.get(f"{BASE_URL}/", headers=HEADERS, timeout=30.0)
            await asyncio.sleep(1)
        except Exception as e:
            logging.warning(f"메인 페이지 접속 실패 (계속 진행): {e}")
        
        try:
            article_urls = await discover_all_articles(client)
        except Exception as e:
            print(f"❌ 아티클 발견 실패: {e}")
            logging.exception("아티클 발견 오류")
            await vector_store.disconnect()
            return False
    
    if not article_urls:
        print("❌ 아티클을 찾을 수 없습니다.")
        await vector_store.disconnect()
        return False
    
    # 테스트용으로 제한
    test_urls = article_urls[:limit]
    print(f"\n3. 테스트 대상: {len(test_urls)}개 아티클 (전체 {len(article_urls)}개 중)")
    
    for i, url in enumerate(test_urls, 1):
        print(f"   {i}. {url}")
    
    print("\n4. 크롤링 테스트 시작...")
    print("-" * 60)
    
    success_count = 0
    fail_count = 0
    
    # 각 아티클 처리 및 저장 (쿠키 유지)
    async with httpx.AsyncClient(
        timeout=30.0, 
        follow_redirects=True,
        cookies={},
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    ) as client:
        # 먼저 메인 페이지에 접속하여 쿠키 받기
        try:
            from scripts.data.crawl_bithumb import BASE_URL, HEADERS
            await client.get(f"{BASE_URL}/", headers=HEADERS, timeout=30.0)
            await asyncio.sleep(1)
        except Exception:
            pass
        for i, article_url in enumerate(test_urls, 1):
            try:
                print(f"\n[{i}/{len(test_urls)}] 크롤링 중: {article_url}")
                
                # 아티클 내용 추출
                article_data = await extract_article_content(client, article_url)
                
                if not article_data:
                    fail_count += 1
                    print(f"⚠️ 내용 추출 실패")
                    continue
                
                if not article_data.get("body"):
                    fail_count += 1
                    print(f"⚠️ 본문이 비어있음")
                    continue
                
                title = article_data["title"][:50]
                body_length = len(article_data["body"])
                images_count = len(article_data.get("images", []))
                
                print(f"   제목: {title}...")
                print(f"   본문 길이: {body_length}자")
                print(f"   이미지 수: {images_count}개")
                
                if images_count > 0:
                    print(f"   이미지 정보:")
                    for img_idx, img in enumerate(article_data["images"][:3], 1):  # 처음 3개만 표시
                        img_url = img.get("url", "")[:60]
                        img_alt = img.get("alt", "")[:30]
                        print(f"     {img_idx}. {img_url}... (alt: {img_alt})")
                
                # 벡터 DB에 저장
                print(f"   벡터 DB 저장 중...")
                if await store_article_to_vector_db(article_data):
                    success_count += 1
                    print(f"✅ 저장 완료: {title[:40]}...")
                else:
                    fail_count += 1
                    print(f"⚠️ 저장 실패")
                
                # Rate limit 방지를 위한 대기
                await asyncio.sleep(0.5)
                
            except Exception as e:
                fail_count += 1
                print(f"❌ 실패: {article_url}")
                print(f"   오류: {str(e)[:100]}")
                logging.exception(f"아티클 처리 오류: {article_url}")
                continue
    
    print("\n" + "=" * 60)
    print(f"✅ 테스트 완료!")
    print(f"   성공: {success_count}개")
    print(f"   실패: {fail_count}개")
    print("=" * 60)
    
    if success_count > 0:
        print("\n✅ 크롤링이 정상적으로 작동합니다!")
        print(f"\n📊 테스트 결과:")
        print(f"   - 발견된 전체 아티클: {len(article_urls)}개")
        print(f"   - 테스트한 아티클: {len(test_urls)}개")
        print(f"   - 성공적으로 저장: {success_count}개")
        print(f"\n💡 전체 크롤링을 실행하려면:")
        print(f"   python scripts/data/crawl_bithumb.py")
    else:
        print("\n❌ 크롤링에 문제가 있습니다.")
        print("   로그를 확인하여 문제를 해결하세요.")
    
    # 연결 해제
    await vector_store.disconnect()
    return success_count > 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='빗썸 FAQ 크롤링 테스트')
    parser.add_argument(
        '--limit',
        type=int,
        default=3,
        help='테스트할 아티클 수 (기본값: 3)'
    )
    
    args = parser.parse_args()
    
    success = asyncio.run(test_crawl(limit=args.limit))
    sys.exit(0 if success else 1)
