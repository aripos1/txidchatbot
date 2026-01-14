"""
빗썸 FAQ 크롤링 스크립트 (Selenium 사용)
Cloudflare 보호를 우회하기 위해 실제 브라우저를 사용합니다.
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Optional, Set
import re
import time

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

# Selenium 설정
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.error("Selenium이 설치되지 않았습니다. pip install selenium 설치 필요")

# Zendesk Help Center 설정
BASE_URL = "https://support.bithumb.com"
LOCALE = "ko"
HELP_CENTER_BASE = f"{BASE_URL}/hc/{LOCALE}"


def create_driver(headless: bool = True):
    """Selenium WebDriver 생성"""
    if not SELENIUM_AVAILABLE:
        raise ImportError("Selenium이 설치되지 않았습니다.")
    
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument('--headless')
    
    # 봇 감지 방지
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        # 봇 감지 방지 스크립트 실행
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        return driver
    except WebDriverException as e:
        logging.error(f"ChromeDriver 오류: {e}")
        logging.error("ChromeDriver가 설치되어 있는지 확인하세요.")
        logging.error("다운로드: https://chromedriver.chromium.org/")
        raise


def extract_images_from_element(soup: BeautifulSoup) -> List[Dict]:
    """요소에서 이미지 정보 추출 (기존 함수 재사용)"""
    from scripts.data.crawl_bithumb import extract_images_from_element as base_extract
    return base_extract(soup)


def discover_all_articles_selenium(driver, limit: Optional[int] = None) -> List[str]:
    """Selenium을 사용하여 모든 아티클 URL 발견"""
    all_articles = set()
    
    try:
        logging.info("메인 페이지 접속 중...")
        driver.get(f"{HELP_CENTER_BASE}")
        
        # 페이지 로드 대기
        time.sleep(3)
        
        # Cloudflare 체크 대기 (필요시)
        try:
            WebDriverWait(driver, 10).until(
                lambda d: "challenges" not in d.current_url.lower()
            )
        except TimeoutException:
            logging.warning("Cloudflare 체크가 감지되었습니다. 수동으로 확인이 필요할 수 있습니다.")
        
        # 페이지 소스 가져오기
        page_source = driver.page_source
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
                driver.get(category_url)
                time.sleep(2)
                
                cat_soup = BeautifulSoup(driver.page_source, 'html.parser')
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
                driver.get(section_url)
                time.sleep(2)
                
                section_soup = BeautifulSoup(driver.page_source, 'html.parser')
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
        driver.get(f"{HELP_CENTER_BASE}")
        time.sleep(2)
        main_soup = BeautifulSoup(driver.page_source, 'html.parser')
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


def extract_article_content_selenium(driver, article_url: str) -> Optional[Dict]:
    """Selenium을 사용하여 아티클 내용 추출"""
    try:
        logging.info(f"아티클 접속: {article_url}")
        driver.get(article_url)
        time.sleep(2)  # 페이지 로드 대기
        
        page_source = driver.page_source
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
    if not SELENIUM_AVAILABLE:
        print("❌ Selenium이 설치되지 않았습니다.")
        print("설치 방법: pip install selenium")
        print("ChromeDriver도 필요합니다: https://chromedriver.chromium.org/")
        return
    
    print("=" * 60)
    print("빗썸 FAQ 크롤링 (Selenium 사용)")
    print("=" * 60)
    
    # MongoDB 연결
    print("\n1. MongoDB Atlas 연결 중...")
    connected = await vector_store.connect()
    if not connected:
        print("❌ MongoDB 연결 실패.")
        return
    
    print("✅ MongoDB 연결 성공!")
    
    # Selenium 드라이버 생성
    print("\n2. 브라우저 시작 중...")
    driver = None
    try:
        driver = create_driver(headless=headless)
        print("✅ 브라우저 시작 완료!")
    except Exception as e:
        print(f"❌ 브라우저 시작 실패: {e}")
        await vector_store.disconnect()
        return
    
    try:
        # 아티클 URL 발견
        print("\n3. 아티클 URL 발견 중...")
        print("-" * 60)
        article_urls = discover_all_articles_selenium(driver, limit=limit)
        
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
                article_data = extract_article_content_selenium(driver, article_url)
                
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
                
                # 벡터 DB에 저장
                if await store_article_to_vector_db(article_data):
                    success_count += 1
                    print(f"✅ 저장 완료: {title[:40]}...")
                else:
                    fail_count += 1
                    print(f"⚠️ 저장 실패")
                
                time.sleep(1)  # Rate limit 방지
                
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
        
    finally:
        # 브라우저 종료
        if driver:
            driver.quit()
            print("\n브라우저 종료 완료")
        
        # MongoDB 연결 해제
        await vector_store.disconnect()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='빗썸 FAQ 크롤링 (Selenium 사용)')
    parser.add_argument('--limit', type=int, default=None, help='크롤링할 아티클 수 제한')
    parser.add_argument('--no-headless', action='store_true', help='헤드리스 모드 비활성화 (브라우저 표시)')
    
    args = parser.parse_args()
    
    asyncio.run(main(limit=args.limit, headless=not args.no_headless))
