"""
벡터 검색 유사도 점수 확인 스크립트
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from chatbot import vector_store, config


async def check_similarity_score(query: str):
    """벡터 검색 유사도 점수 확인"""
    print(f"\n{'='*60}")
    print(f"검색 쿼리: {query}")
    print(f"{'='*60}\n")
    
    # 벡터 스토어 연결
    if not await vector_store.connect():
        print("❌ MongoDB 연결 실패")
        return
    
    try:
        # 벡터 검색 수행
        results = await vector_store.search(query, limit=5)
        
        if not results:
            print("⚠️ 검색 결과가 없습니다.")
            return
        
        print(f"📊 검색 결과: {len(results)}개\n")
        print(f"🔍 유사도 임계값: {config.SIMILARITY_THRESHOLD}\n")
        print("-" * 60)
        
        for i, result in enumerate(results, 1):
            score = result.get("score", 0.0)
            text = result.get("text", "")
            source = result.get("source", "")
            passed = score > config.SIMILARITY_THRESHOLD
            
            status = "✅ 통과" if passed else "❌ 미통과"
            
            print(f"\n[{i}] {status}")
            print(f"  점수: {score:.4f}")
            print(f"  임계값: {config.SIMILARITY_THRESHOLD}")
            print(f"  차이: {score - config.SIMILARITY_THRESHOLD:+.4f}")
            print(f"  출처: {source}")
            print(f"  내용 미리보기: {text[:100]}...")
            print("-" * 60)
        
        # 최고 점수 요약
        top_score = results[0].get("score", 0.0) if results else 0.0
        will_use_db = top_score > config.SIMILARITY_THRESHOLD
        
        print(f"\n📈 요약:")
        print(f"  최고 점수: {top_score:.4f}")
        print(f"  DB 사용 여부: {'✅ 사용' if will_use_db else '❌ Deep Research'}")
        print(f"  Deep Research 여부: {'❌ 건너뜀' if will_use_db else '✅ 수행'}")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await vector_store.disconnect()


async def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="벡터 검색 유사도 점수 확인")
    parser.add_argument(
        "query",
        nargs="?",
        default="입금이 안돼요",
        help="검색할 질문 (기본값: '입금이 안돼요')"
    )
    
    args = parser.parse_args()
    
    await check_similarity_score(args.query)


if __name__ == "__main__":
    asyncio.run(main())

