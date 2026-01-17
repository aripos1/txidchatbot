"""
Utility 라우터 (health, robots.txt, sitemap 등)
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse, Response
import os
import time
from datetime import datetime

from src.blog.posts import BLOG_POSTS

router = APIRouter(prefix="", tags=["utility"])

def register_utility_routes(app):
    """Utility 라우트를 FastAPI 앱에 등록"""
    
    @app.get("/health")
    async def health_check():
        """헬스 체크 엔드포인트"""
        return {"status": "healthy", "timestamp": time.time()}
    
    @app.get("/favicon.ico")
    async def favicon():
        """파비콘 제공"""
        favicon_path = "static/favicon.ico"
        if os.path.exists(favicon_path):
            return FileResponse(favicon_path, media_type="image/x-icon")
        else:
            return Response(status_code=404)
    
    @app.get("/apple-touch-icon.png")
    async def apple_touch_icon():
        """Apple Touch Icon 제공"""
        icon_path = "static/apple-touch-icon.png"
        if os.path.exists(icon_path):
            return FileResponse(icon_path, media_type="image/png")
        else:
            return Response(status_code=404)
    
    @app.get("/robots.txt")
    async def robots_txt():
        """robots.txt 파일 제공"""
        robots_path = "static/robots.txt"
        if os.path.exists(robots_path):
            return FileResponse(robots_path, media_type="text/plain")
        else:
            return Response(content="User-agent: *\nAllow: /", media_type="text/plain")
    
    @app.get("/sitemap.xml")
    async def sitemap_xml():
        """동적으로 sitemap.xml 생성 (블로그 포스트 포함)"""
        base_url = "https://txid.shop"
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 기본 sitemap XML 시작
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
            '        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            '        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9',
            '        http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">',
            '',
            '    <!-- 메인 페이지 -->',
            '    <url>',
            f'        <loc>{base_url}/</loc>',
            f'        <lastmod>{today}</lastmod>',
            '        <changefreq>daily</changefreq>',
            '        <priority>1.0</priority>',
            '    </url>',
            '',
            '    <!-- 챗봇 페이지 -->',
            '    <url>',
            f'        <loc>{base_url}/chat</loc>',
            f'        <lastmod>{today}</lastmod>',
            '        <changefreq>weekly</changefreq>',
            '        <priority>0.9</priority>',
            '    </url>',
            '',
            '    <!-- 블로그 목록 -->',
            '    <url>',
            f'        <loc>{base_url}/blog</loc>',
            f'        <lastmod>{today}</lastmod>',
            '        <changefreq>weekly</changefreq>',
            '        <priority>0.9</priority>',
            '    </url>',
            '',
        ]
        
        # 블로그 포스트들 추가 (우선순위 0.8)
        for post_slug in BLOG_POSTS.keys():
            xml_parts.extend([
                f'    <!-- 블로그 포스트: {post_slug} -->',
                '    <url>',
                f'        <loc>{base_url}/blog/{post_slug}</loc>',
                f'        <lastmod>{today}</lastmod>',
                '        <changefreq>monthly</changefreq>',
                '        <priority>0.8</priority>',
                '    </url>',
                '',
            ])
        
        # 기타 페이지들
        xml_parts.extend([
            '    <!-- 스테이킹 계산기 -->',
            '    <url>',
            f'        <loc>{base_url}/stk</loc>',
            f'        <lastmod>{today}</lastmod>',
            '        <changefreq>monthly</changefreq>',
            '        <priority>0.8</priority>',
            '    </url>',
            '',
            '    <!-- 입출금 가이드 -->',
            '    <url>',
            f'        <loc>{base_url}/compliance</loc>',
            f'        <lastmod>{today}</lastmod>',
            '        <changefreq>monthly</changefreq>',
            '        <priority>0.7</priority>',
            '    </url>',
            '',
            '    <!-- 빗썸 API 가이드 -->',
            '    <url>',
            f'        <loc>{base_url}/bithumb-guide</loc>',
            f'        <lastmod>{today}</lastmod>',
            '        <changefreq>monthly</changefreq>',
            '        <priority>0.7</priority>',
            '    </url>',
            '',
            '    <!-- 개인정보처리방침 -->',
            '    <url>',
            f'        <loc>{base_url}/privacy-policy</loc>',
            f'        <lastmod>{today}</lastmod>',
            '        <changefreq>yearly</changefreq>',
            '        <priority>0.5</priority>',
            '    </url>',
            '',
            '    <!-- 이용약관 -->',
            '    <url>',
            f'        <loc>{base_url}/terms-of-service</loc>',
            f'        <lastmod>{today}</lastmod>',
            '        <changefreq>yearly</changefreq>',
            '        <priority>0.5</priority>',
            '    </url>',
            '',
            '</urlset>',
        ])
        
        xml_content = '\n'.join(xml_parts)
        return Response(content=xml_content, media_type="application/xml")
