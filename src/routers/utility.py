"""
Utility 라우터 (health, robots.txt, sitemap 등)
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse, Response
import os
import time

router = APIRouter(prefix="", tags=["utility"])

def register_utility_routes(app):
    """Utility 라우트를 FastAPI 앱에 등록"""
    
    @app.get("/health")
    async def health_check():
        """헬스 체크 엔드포인트"""
        return {"status": "healthy", "timestamp": time.time()}
    
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
        """sitemap.xml 파일 제공"""
        sitemap_path = "static/sitemap.xml"
        if os.path.exists(sitemap_path):
            return FileResponse(sitemap_path, media_type="application/xml")
        else:
            return Response(content="<?xml version='1.0' encoding='UTF-8'?><urlset></urlset>", media_type="application/xml")
