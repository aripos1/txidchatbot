"""
빗썸 FAQ 크롤링 테스트 스크립트 (Playwright 사용)
소수의 아티클만 크롤링하여 기능을 테스트합니다.
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.data.crawl_bithumb_playwright import (
    main,
    PLAYWRIGHT_AVAILABLE
)

if __name__ == "__main__":
    import argparse
    
    if not PLAYWRIGHT_AVAILABLE:
        print("❌ Playwright가 설치되지 않았습니다.")
        print("\n설치 방법:")
        print("  1. pip install playwright")
        print("  2. playwright install chromium")
        sys.exit(1)
    
    parser = argparse.ArgumentParser(description='빗썸 FAQ 크롤링 테스트 (Playwright 사용)')
    parser.add_argument(
        '--limit',
        type=int,
        default=3,
        help='테스트할 아티클 수 (기본값: 3)'
    )
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='헤드리스 모드 비활성화 (브라우저 표시)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("빗썸 FAQ 크롤링 테스트 (Playwright)")
    print("=" * 60)
    print(f"테스트 아티클 수: {args.limit}개")
    print(f"헤드리스 모드: {not args.no_headless}")
    print("=" * 60)
    print()
    
    success = asyncio.run(main(limit=args.limit, headless=not args.no_headless))
    sys.exit(0 if success else 1)
