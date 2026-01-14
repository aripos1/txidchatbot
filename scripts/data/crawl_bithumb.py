"""
빗썸 고객지원 페이지 크롤링 및 벡터 DB 저장 스크립트
Zendesk Help Center 웹 크롤링을 통해 FAQ를 체계적으로 수집합니다.
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Set, Optional
import re

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from chatbot.vector_store import vector_store
import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Zendesk Help Center 설정
BASE_URL = "https://support.bithumb.com"
LOCALE = "ko"
HELP_CENTER_BASE = f"{BASE_URL}/hc/{LOCALE}"

# 요청 헤더 (봇 차단 우회를 위해 실제 브라우저처럼 설정)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "Referer": "https://www.bithumb.com/",
}


async def fetch_page(client: httpx.AsyncClient, url: str, referer: str = None) -> Optional[BeautifulSoup]:
    """웹 페이지를 가져와서 BeautifulSoup 객체로 반환"""
    try:
        # Referer 헤더 추가 (403 오류 방지)
        headers = HEADERS.copy()
        if referer:
            headers["Referer"] = referer
        elif BASE_URL in url:
            headers["Referer"] = f"{BASE_URL}/"
        
        # 쿠키와 세션 유지를 위한 설정
        response = await client.get(
            url, 
            headers=headers, 
            timeout=30.0, 
            follow_redirects=True,
            cookies=client.cookies  # 쿠키 유지
        )
        
        # 403 오류 시 재시도 (더 긴 대기 시간)
        if response.status_code == 403:
            logging.warning(f"403 오류 발생, 3초 대기 후 재시도: {url}")
            await asyncio.sleep(3)
            
            # User-Agent를 약간 변경하여 재시도
            retry_headers = headers.copy()
            retry_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            
            response = await client.get(
                url,
                headers=retry_headers,
                timeout=30.0,
                follow_redirects=True,
                cookies=client.cookies
            )
        
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logging.error(f"403 Forbidden 오류 ({url}) - 웹사이트가 크롤러를 차단하고 있습니다.")
            logging.error("해결 방법:")
            logging.error("1. 브라우저에서 직접 접속하여 확인")
            logging.error("2. User-Agent를 업데이트")
            logging.error("3. 쿠키/세션 설정 확인")
        else:
            logging.warning(f"HTTP 오류 ({url}): {e.response.status_code}")
        return None
    except Exception as e:
        logging.warning(f"페이지 가져오기 실패 ({url}): {e}")
        return None


async def discover_categories(client: httpx.AsyncClient) -> Set[str]:
    """모든 카테고리 URL 발견"""
    categories = set()
    
    # 메인 페이지에서 카테고리 링크 찾기 (Referer 추가)
    soup = await fetch_page(client, f"{HELP_CENTER_BASE}", referer="https://www.bithumb.com/")
    if not soup:
        return categories
    
    # 카테고리 링크 찾기
    category_links = soup.find_all('a', href=re.compile(r'/hc/' + LOCALE + r'/categories/\d+'))
    
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
    return categories


async def discover_sections(client: httpx.AsyncClient, category_url: str) -> Set[str]:
    """카테고리에서 모든 섹션 URL 발견"""
    sections = set()
    
    soup = await fetch_page(client, category_url)
    if not soup:
        return sections
    
    # 섹션 링크 찾기
    section_links = soup.find_all('a', href=re.compile(r'/hc/' + LOCALE + r'/sections/\d+'))
    
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
                sections.add(full_url)
    
    return sections


async def discover_articles_from_section(client: httpx.AsyncClient, section_url: str) -> Set[str]:
    """섹션에서 모든 아티클 URL 발견"""
    articles = set()
    
    soup = await fetch_page(client, section_url)
    if not soup:
        return articles
    
    # 아티클 링크 찾기
    article_links = soup.find_all('a', href=re.compile(r'/hc/' + LOCALE + r'/articles/\d+'))
    
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
                articles.add(full_url)
    
    return articles


async def discover_all_articles(client: httpx.AsyncClient) -> List[str]:
    """모든 아티클 URL을 체계적으로 발견"""
    all_articles = set()
    
    # 1. 카테고리 발견
    logging.info("카테고리 발견 중...")
    categories = await discover_categories(client)
    
    # 2. 각 카테고리에서 섹션 발견
    all_sections = set()
    for category_url in categories:
        logging.info(f"카테고리에서 섹션 발견 중: {category_url}")
        sections = await discover_sections(client, category_url)
        all_sections.update(sections)
        await asyncio.sleep(0.3)  # Rate limit 방지
    
    logging.info(f"발견된 섹션 수: {len(all_sections)}")
    
    # 3. 각 섹션에서 아티클 발견
    for section_url in all_sections:
        logging.info(f"섹션에서 아티클 발견 중: {section_url}")
        articles = await discover_articles_from_section(client, section_url)
        all_articles.update(articles)
        await asyncio.sleep(0.3)  # Rate limit 방지
    
    # 4. 메인 페이지에서도 직접 아티클 링크 찾기
    logging.info("메인 페이지에서 아티클 발견 중...")
    main_soup = await fetch_page(client, f"{HELP_CENTER_BASE}")
    if main_soup:
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


def extract_images_from_element(elem) -> List[Dict]:
    """요소에서 이미지 정보 추출"""
    images = []
    
    if not elem:
        return images
    
    # 모든 img 태그 찾기
    img_tags = elem.find_all('img')
    
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
        # 부모 요소에서 figcaption, caption 클래스 찾기
        parent = img.find_parent(['figure', 'div', 'p'])
        if parent:
            caption = parent.find(class_=re.compile(r'caption|figcaption|image.*caption', re.I))
            if caption:
                caption_text = caption.get_text(strip=True)
                if caption_text:
                    img_info['caption'] = caption_text
            
            # 이미지 앞뒤 텍스트도 포함 (설명일 수 있음)
            img_text_parts = []
            
            # 이미지 앞 텍스트
            prev_sibling = img.find_previous_sibling(['p', 'div', 'span'])
            if prev_sibling:
                prev_text = prev_sibling.get_text(strip=True)
                if prev_text and len(prev_text) < 200:  # 너무 긴 텍스트는 제외
                    img_text_parts.append(prev_text)
            
            # 이미지 뒤 텍스트
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


async def extract_article_content(client: httpx.AsyncClient, article_url: str) -> Optional[Dict]:
    """아티클 페이지에서 제목, 본문, 이미지 추출"""
    soup = await fetch_page(client, article_url)
    if not soup:
        return None
    
    try:
        # 제목 추출 (일반적으로 h1 태그 또는 article-title 클래스)
        title_elem = soup.find('h1') or soup.find(class_=re.compile(r'article.*title|title.*article', re.I))
        title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
        
        # 본문 추출 (일반적으로 article-body 클래스 또는 article 태그)
        body_elem = (
            soup.find(class_=re.compile(r'article.*body|body.*article', re.I)) or
            soup.find('article') or
            soup.find(id=re.compile(r'article.*content|content.*article', re.I))
        )
        
        images = []
        body_text = ""
        
        if body_elem:
            # 이미지 정보 추출 (태그 제거 전에 수행)
            images = extract_images_from_element(body_elem)
            
            # 불필요한 태그 제거
            for tag in body_elem(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            
            body_text = body_elem.get_text(separator='\n', strip=True)
        else:
            # 본문을 찾지 못한 경우 전체 페이지에서 추출
            main_content = soup.find('main') or soup.find('div', class_=re.compile(r'content|main', re.I))
            if main_content:
                # 이미지 정보 추출
                images = extract_images_from_element(main_content)
                
                for tag in main_content(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                    tag.decompose()
                body_text = main_content.get_text(separator='\n', strip=True)
            else:
                # 전체 페이지에서 이미지 추출
                images = extract_images_from_element(soup)
                body_text = soup.get_text(separator='\n', strip=True)
        
        # 여러 공백/줄바꿈 정리
        lines = [line.strip() for line in body_text.split('\n') if line.strip()]
        clean_body = '\n'.join(lines)
        
        # 이미지 설명을 텍스트에 추가 (검색 가능하게 만들기)
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
        
        # 이미지 설명을 본문에 추가
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
            "images": images,  # 이미지 정보 추가
            "full_text": f"제목: {title}\n\n{clean_body}"
        }
        
    except Exception as e:
        logging.error(f"아티클 내용 추출 실패 ({article_url}): {e}")
        return None


async def store_article_to_vector_db(article_data: Dict):
    """아티클을 벡터 DB에 저장"""
    if vector_store.collection is None:
        logging.error("MongoDB가 연결되지 않았습니다.")
        return False
    
    try:
        # 텍스트를 청크로 분할
        text = article_data["full_text"]
        chunks = vector_store.split_text(text, chunk_size=1000, overlap=200)
        
        stored_count = 0
        for i, chunk in enumerate(chunks):
            try:
                # 임베딩 생성
                embedding = await vector_store.create_embedding(chunk)
                if not embedding:
                    continue
                
                # 문서 ID 생성
                import hashlib
                doc_id = hashlib.md5(
                    f"zendesk_{article_data['article_id']}_{i}".encode()
                ).hexdigest()
                
                # 이미지 정보를 메타데이터에 포함
                metadata = {
                    "article_id": article_data.get("article_id"),
                    "title": article_data["title"],
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "type": "zendesk_article",
                    "created_at": datetime.utcnow().isoformat()
                }
                
                # 청크에 이미지가 포함된 경우 이미지 정보 추가
                # (이미지 설명이 청크에 포함되어 있을 수 있음)
                if article_data.get("images"):
                    # 현재 청크의 위치를 기반으로 관련 이미지 찾기
                    chunk_start = sum(len(chunks[j]) for j in range(i))
                    chunk_end = chunk_start + len(chunk)
                    
                    # 전체 텍스트에서 이미지 설명의 위치를 추정
                    # (간단한 방법: 모든 이미지를 메타데이터에 포함)
                    if i == 0:  # 첫 번째 청크에만 이미지 정보 포함 (중복 방지)
                        metadata["images"] = article_data["images"]
                
                # MongoDB에 저장
                document = {
                    "_id": doc_id,
                    "text": chunk,
                    "source": article_data["url"],
                    "metadata": metadata,
                    "embedding": embedding,
                    "created_at": datetime.utcnow()
                }
                
                await vector_store.collection.update_one(
                    {"_id": doc_id},
                    {"$set": document},
                    upsert=True
                )
                
                stored_count += 1
                
            except Exception as e:
                logging.error(f"청크 저장 실패 (아티클 {article_data.get('article_id')}, 청크 {i}): {e}")
                continue
        
        logging.info(f"아티클 {article_data.get('article_id')} 저장 완료: {stored_count}/{len(chunks)} 청크")
        return stored_count > 0
        
    except Exception as e:
        logging.error(f"아티클 저장 실패 ({article_data.get('article_id')}): {e}")
        return False


async def main():
    """메인 함수"""
    print("=" * 60)
    print("빗썸 고객지원 센터 FAQ 크롤링 (웹 크롤링)")
    print("=" * 60)
    
    # MongoDB 연결
    print("\n1. MongoDB Atlas 연결 중...")
    connected = await vector_store.connect()
    if not connected:
        print("❌ MongoDB 연결 실패. 연결 설정을 확인해주세요.")
        return
    
    print("✅ MongoDB 연결 성공!")
    
    # 아티클 URL 발견
    print("\n2. 아티클 URL 발견 중...")
    print("   (카테고리 → 섹션 → 아티클 순서로 탐색)")
    print("   (이 작업은 몇 분 걸릴 수 있습니다...)")
    print("-" * 60)
    
    # 쿠키와 세션을 유지하기 위한 클라이언트 설정
    async with httpx.AsyncClient(
        timeout=30.0, 
        follow_redirects=True,
        cookies={},  # 쿠키 저장소 초기화
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    ) as client:
        # 먼저 메인 페이지에 접속하여 쿠키 받기
        try:
            logging.info("메인 페이지 접속하여 쿠키 받는 중...")
            await client.get(f"{BASE_URL}/", headers=HEADERS, timeout=30.0)
            await asyncio.sleep(1)  # 쿠키 설정 대기
        except Exception as e:
            logging.warning(f"메인 페이지 접속 실패 (계속 진행): {e}")
        
        article_urls = await discover_all_articles(client)
    
    if not article_urls:
        print("❌ 아티클을 찾을 수 없습니다.")
        await vector_store.disconnect()
        return
    
    print(f"\n3. 총 {len(article_urls)}개 아티클 발견")
    print("   아티클 내용 크롤링 및 벡터 DB 저장 시작...")
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
            await client.get(f"{BASE_URL}/", headers=HEADERS, timeout=30.0)
            await asyncio.sleep(1)
        except Exception:
            pass
        
        for i, article_url in enumerate(article_urls, 1):
            try:
                print(f"\n[{i}/{len(article_urls)}] 크롤링 중: {article_url}")
                
                # 아티클 내용 추출
                article_data = await extract_article_content(client, article_url)
                
                if not article_data or not article_data.get("body"):
                    fail_count += 1
                    print(f"⚠️ 내용 추출 실패: {article_url}")
                    continue
                
                title = article_data["title"][:50]
                print(f"   제목: {title}...")
                
                # 벡터 DB에 저장
                if await store_article_to_vector_db(article_data):
                    success_count += 1
                    print(f"✅ 완료: {title[:40]}...")
                else:
                    fail_count += 1
                    print(f"⚠️ 저장 실패: {title[:40]}...")
                
                # Rate limit 방지를 위한 대기
                await asyncio.sleep(0.5)
                
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
    
    print("\n📌 다음 단계:")
    print("1. MongoDB Atlas에서 벡터 검색 인덱스가 생성되었는지 확인")
    print("2. FAQ Specialist에서 DB 검색을 활성화하면 더 정확한 답변 가능")
    print("3. 정기적으로 FAQ 페이지를 업데이트하여 최신 정보 유지")
    
    # 연결 해제
    await vector_store.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

