"""
블로그 라우터
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.blog.posts import BLOG_POSTS

# 템플릿은 main.py에서 전역으로 설정되므로 여기서는 파라미터로 받음
router = APIRouter(prefix="", tags=["blog"])

def register_blog_routes(app, templates: Jinja2Templates):
    """블로그 라우트를 FastAPI 앱에 등록"""
    
    @app.get("/blog", response_class=HTMLResponse)
    async def blog_page(request: Request):
        """블로그 목록 페이지"""
        return templates.TemplateResponse("content/blog.html", {"request": request})
    
    @app.get("/blog/{post_slug}", response_class=HTMLResponse)
    async def blog_post_page(request: Request, post_slug: str):
        """블로그 포스트 페이지"""
        if post_slug not in BLOG_POSTS:
            raise HTTPException(status_code=404, detail="Post not found")
        
        post = BLOG_POSTS[post_slug].copy()
        
        # 이전/다음 포스트 찾기
        post_keys = list(BLOG_POSTS.keys())
        current_index = post_keys.index(post_slug) if post_slug in post_keys else -1
        
        if current_index > 0:
            prev_key = post_keys[current_index - 1]
            post["prev"] = {
                "url": f"/blog/{prev_key}",
                "title": BLOG_POSTS[prev_key]["title"]
            }
        
        if current_index < len(post_keys) - 1:
            next_key = post_keys[current_index + 1]
            post["next"] = {
                "url": f"/blog/{next_key}",
                "title": BLOG_POSTS[next_key]["title"]
            }
        
        return templates.TemplateResponse("content/blog_post.html", {"request": request, "post": post})
