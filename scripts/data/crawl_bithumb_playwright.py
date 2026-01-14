"""
빗썸 FAQ 크롤링 스크립트 (Playwright 사용)
Cloudflare 보호를 우회하기 위해 실제 브라우저를 사용합니다.
Playwright는 Selenium보다 빠르고 안정적입니다.
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Optional, Set
import re

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from chatbot.vector_store import vector_store
import logging
from bs4 import BeautifulSoup
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Playwright 설정
try:
    from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.error("Playwright가 설치되지 않았습니다. pip install playwright && playwright install chromium 설치 필요")

# Zendesk Help Center 설정
BASE_URL = "https://support.bithumb.com"
LOCALE = "ko"
HELP_CENTER_BASE = f"{BASE_URL}/hc/{LOCALE}"


def extract_images_from_element(soup: BeautifulSoup) -> List[Dict]:
    """요소에서 이미지 정보 추출"""
    images = []
    
    if not soup:
        return images
    
    # 모든 img 태그 찾기
    img_tags = soup.find_all('img')
    
    for img in img_tags:
        img_info = {}
        
        # 이미지 URL 추출
        img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
        if img_url:
            # 상대 경로를 절대 경로로 변환
            if img_url.startswith('//'):
                img_url = f"https:{img_url}"
            elif img_url.startswith('/'):
                img_url = f"{BASE_URL}{img_url}"
            elif not img_url.startswith('http'):
                continue
            
            img_info['url'] = img_url
        
        # Alt 텍스트 추출
        alt_text = img.get('alt', '').strip()
        if alt_text:
            img_info['alt'] = alt_text
        
        # Title 속성 추출
        title_text = img.get('title', '').strip()
        if title_text:
            img_info['title'] = title_text
        
        # 이미지 주변 텍스트 (캡션, 설명) 추출
        parent = img.find_parent(['figure', 'div', 'p'])
        if parent:
            caption = parent.find(class_=re.compile(r'caption|figcaption|image.*caption', re.I))
            if caption:
                caption_text = caption.get_text(strip=True)
                if caption_text:
                    img_info['caption'] = caption_text
            
            # 이미지 앞뒤 텍스트도 포함
            img_text_parts = []
            
            prev_sibling = img.find_previous_sibling(['p', 'div', 'span'])
            if prev_sibling:
                prev_text = prev_sibling.get_text(strip=True)
                if prev_text and len(prev_text) < 200:
                    img_text_parts.append(prev_text)
            
            next_sibling = img.find_next_sibling(['p', 'div', 'span'])
            if next_sibling:
                next_text = next_sibling.get_text(strip=True)
                if next_text and len(next_text) < 200:
                    img_text_parts.append(next_text)
            
            if img_text_parts:
                img_info['context'] = ' '.join(img_text_parts)
        
        if img_info:
            images.append(img_info)
    
    return images


async def discover_all_articles_playwright(page: Page, limit: Optional[int] = None) -> List[str]:
    """Playwright를 사용하여 모든 아티클 URL 발견"""
    all_articles = set()
    
    try:
        logging.info("메인 페이지 접속 중...")
        await page.goto(f"{HELP_CENTER_BASE}", wait_until="networkidle", timeout=30000)
        
        # Cloudflare 체크 대기 (필요시)
        await asyncio.sleep(2)
        
        # 페이지 소스 가져오기
        page_source = await page.content()
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # 카테고리 링크 찾기
        category_links = soup.find_all('a', href=re.compile(r'/hc/' + LOCALE + r'/categories/\d+'))
        categories = set()
        for link in category_links:
            href = link.get('href', '')
            if href:
                if href.startswith('/'):
                    full_url = f"{BASE_URL}{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                if '/categories/' in full_url:
                    categories.add(full_url)
        
        logging.info(f"발견된 카테고리 수: {len(categories)}")
        
        # 각 카테고리에서 섹션 찾기
        all_sections = set()
        for category_url in list(categories)[:10]:  # 처음 10개만 (테스트용)
            try:
                logging.info(f"카테고리 접속: {category_url}")
                await page.goto(category_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(1)
                
                cat_soup = BeautifulSoup(await page.content(), 'html.parser')
                section_links = cat_soup.find_all('a', href=re.compile(r'/hc/' + LOCALE + r'/sections/\d+'))
                
                for link in section_links:
                    href = link.get('href', '')
                    if href:
                        if href.startswith('/'):
                            full_url = f"{BASE_URL}{href}"
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            continue
                        if '/sections/' in full_url:
                            all_sections.add(full_url)
            except Exception as e:
                logging.warning(f"카테고리 처리 실패 ({category_url}): {e}")
                continue
        
        logging.info(f"발견된 섹션 수: {len(all_sections)}")
        
        # 각 섹션에서 아티클 찾기
        for section_url in list(all_sections)[:20]:  # 처음 20개만 (테스트용)
            try:
                logging.info(f"섹션 접속: {section_url}")
                await page.goto(section_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(1)
                
                section_soup = BeautifulSoup(await page.content(), 'html.parser')
                article_links = section_soup.find_all('a', href=re.compile(r'/hc/' + LOCALE + r'/articles/\d+'))
                
                for link in article_links:
                    href = link.get('href', '')
                    if href:
                        if href.startswith('/'):
                            full_url = f"{BASE_URL}{href}"
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            continue
                        if '/articles/' in full_url:
                            all_articles.add(full_url)
                            
                        if limit and len(all_articles) >= limit:
                            break
                
                if limit and len(all_articles) >= limit:
                    break
            except Exception as e:
                logging.warning(f"섹션 처리 실패 ({section_url}): {e}")
                continue
        
        # 메인 페이지에서도 직접 아티클 링크 찾기
        await page.goto(f"{HELP_CENTER_BASE}", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(1)
        main_soup = BeautifulSoup(await page.content(), 'html.parser')
        main_article_links = main_soup.find_all('a', href=re.compile(r'/hc/' + LOCALE + r'/articles/\d+'))
        for link in main_article_links:
            href = link.get('href', '')
            if href:
                if href.startswith('/'):
                    full_url = f"{BASE_URL}{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                if '/articles/' in full_url:
                    all_articles.add(full_url)
        
        logging.info(f"총 발견된 아티클 수: {len(all_articles)}")
        return list(all_articles)
        
    except Exception as e:
        logging.error(f"아티클 발견 실패: {e}")
        return []


async def extract_article_content_playwright(page: Page, article_url: str) -> Optional[Dict]:
    """Playwright를 사용하여 아티클 내용 추출"""
    try:
        logging.info(f"아티클 접속: {article_url}")
        await page.goto(article_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(1)  # 페이지 로드 대기
        
        page_source = await page.content()
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # 제목 추출
        title_elem = soup.find('h1') or soup.find(class_=re.compile(r'article.*title|title.*article', re.I))
        title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
        
        # 본문 추출
        body_elem = (
            soup.find(class_=re.compile(r'article.*body|body.*article', re.I)) or
            soup.find('article') or
            soup.find(id=re.compile(r'article.*content|content.*article', re.I))
        )
        
        images = []
        body_text = ""
        
        if body_elem:
            images = extract_images_from_element(body_elem)
            for tag in body_elem(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            body_text = body_elem.get_text(separator='\n', strip=True)
        else:
            main_content = soup.find('main') or soup.find('div', class_=re.compile(r'content|main', re.I))
            if main_content:
                images = extract_images_from_element(main_content)
                for tag in main_content(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                    tag.decompose()
                body_text = main_content.get_text(separator='\n', strip=True)
            else:
                images = extract_images_from_element(soup)
                body_text = soup.get_text(separator='\n', strip=True)
        
        # 텍스트 정리
        lines = [line.strip() for line in body_text.split('\n') if line.strip()]
        clean_body = '\n'.join(lines)
        
        # 이미지 설명 추가
        image_descriptions = []
        for img in images:
            img_desc_parts = []
            if img.get('alt'):
                img_desc_parts.append(f"[이미지 설명: {img['alt']}]")
            if img.get('caption'):
                img_desc_parts.append(f"[이미지 캡션: {img['caption']}]")
            if img.get('context'):
                img_desc_parts.append(f"[이미지 주변 설명: {img['context']}]")
            if img_desc_parts:
                image_descriptions.append(' '.join(img_desc_parts))
        
        if image_descriptions:
            clean_body += "\n\n" + "\n".join(image_descriptions)
        
        # 아티클 ID 추출
        article_id_match = re.search(r'/articles/(\d+)', article_url)
        article_id = article_id_match.group(1) if article_id_match else None
        
        return {
            "url": article_url,
            "title": title,
            "body": clean_body,
            "article_id": article_id,
            "images": images,
            "full_text": f"제목: {title}\n\n{clean_body}"
        }
        
    except Exception as e:
        logging.error(f"아티클 내용 추출 실패 ({article_url}): {e}")
        return None


async def store_article_to_vector_db(article_data: Dict):
    """아티클을 벡터 DB에 저장 (기존 함수 재사용)"""
    from scripts.data.crawl_bithumb import store_article_to_vector_db as base_store
    return await base_store(article_data)


async def main(limit: Optional[int] = None, headless: bool = True):
    """메인 함수"""
    if not PLAYWRIGHT_AVAILABLE:
        print("❌ Playwright가 설치되지 않았습니다.")
        print("설치 방법:")
        print("  1. pip install playwright")
        print("  2. playwright install chromium")
        return
    
    print("=" * 60)
    print("빗썸 FAQ 크롤링 (Playwright 사용)")
    print("=" * 60)
    
    # MongoDB 연결
    print("\n1. MongoDB Atlas 연결 중...")
    connected = await vector_store.connect()
    if not connected:
        print("❌ MongoDB 연결 실패.")
        return
    
    print("✅ MongoDB 연결 성공!")
    
    # Playwright 브라우저 시작
    print("\n2. 브라우저 시작 중...")
    async with async_playwright() as p:
        try:
            # 브라우저 실행 (봇 감지 방지 옵션 포함)
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            )
            
            # 컨텍스트 생성 (봇 감지 방지)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='ko-KR',
                timezone_id='Asia/Seoul',
            )
            
            # 봇 감지 방지 스크립트 추가
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = {
                    runtime: {}
                };
            """)
            
            page = await context.new_page()
            print("✅ 브라우저 시작 완료!")
            
            try:
                # 아티클 URL 발견
                print("\n3. 아티클 URL 발견 중...")
                print("-" * 60)
                article_urls = await discover_all_articles_playwright(page, limit=limit)
                
                if not article_urls:
                    print("❌ 아티클을 찾을 수 없습니다.")
                    return
                
                if limit:
                    article_urls = article_urls[:limit]
                
                print(f"\n4. 총 {len(article_urls)}개 아티클 발견")
                print("   크롤링 및 벡터 DB 저장 시작...")
                print("-" * 60)
                
                success_count = 0
                fail_count = 0
                
                # 각 아티클 처리 및 저장
                for i, article_url in enumerate(article_urls, 1):
                    try:
                        print(f"\n[{i}/{len(article_urls)}] 크롤링 중: {article_url}")
                        
                        # 아티클 내용 추출
                        article_data = await extract_article_content_playwright(page, article_url)
                        
                        if not article_data or not article_data.get("body"):
                            fail_count += 1
                            print(f"⚠️ 내용 추출 실패")
                            continue
                        
                        title = article_data["title"][:50]
                        body_length = len(article_data["body"])
                        images_count = len(article_data.get("images", []))
                        
                        print(f"   제목: {title}...")
                        print(f"   본문 길이: {body_length}자")
                        print(f"   이미지 수: {images_count}개")
                        
                        if images_count > 0:
                            print(f"   이미지 정보:")
                            for img_idx, img in enumerate(article_data["images"][:3], 1):
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
                        
                        await asyncio.sleep(1)  # Rate limit 방지
                        
                    except Exception as e:
                        fail_count += 1
                        print(f"❌ 실패: {article_url} - {e}")
                        logging.exception(f"아티클 처리 오류: {article_url}")
                        continue
                
                print("\n" + "=" * 60)
                print(f"✅ 크롤링 완료!")
                print(f"   성공: {success_count}개")
                print(f"   실패: {fail_count}개")
                print("=" * 60)
                
                if success_count > 0:
                    print("\n✅ 크롤링이 정상적으로 작동합니다!")
                    print(f"\n📊 결과:")
                    print(f"   - 발견된 아티클: {len(article_urls)}개")
                    print(f"   - 성공적으로 저장: {success_count}개")
                    print(f"\n💡 전체 크롤링을 실행하려면:")
                    print(f"   python scripts/data/crawl_bithumb_playwright.py")
                
            finally:
                await page.close()
                await context.close()
                await browser.close()
                print("\n브라우저 종료 완료")
        
        except Exception as e:
            logging.error(f"브라우저 실행 오류: {e}")
            print(f"❌ 브라우저 실행 실패: {e}")
    
    # MongoDB 연결 해제
    await vector_store.disconnect()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='빗썸 FAQ 크롤링 (Playwright 사용)')
    parser.add_argument('--limit', type=int, default=None, help='크롤링할 아티클 수 제한')
    parser.add_argument('--no-headless', action='store_true', help='헤드리스 모드 비활성화 (브라우저 표시)')
    
    args = parser.parse_args()
    
    asyncio.run(main(limit=args.limit, headless=not args.no_headless))
