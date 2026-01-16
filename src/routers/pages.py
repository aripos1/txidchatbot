"""
Pages 라우터 (정적 페이지들)
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.services.chain_configs import get_chain_configs
from chatbot import config

router = APIRouter(prefix="", tags=["pages"])

def register_pages_routes(app, templates: Jinja2Templates):
    """Pages 라우트를 FastAPI 앱에 등록"""
    
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        """홈 페이지"""
        excluded_chains = ["litecoin", "dogecoin"]
        CHAIN_CONFIGS = get_chain_configs()
        supported_chains = [
            {"name": config["name"], "symbol": config["symbol"]} 
            for key, config in CHAIN_CONFIGS.items() 
            if "name" in config and key not in excluded_chains
        ]
        return templates.TemplateResponse("pages/explorer_ui.html", {"request": request, "supported_chains": supported_chains})
    
    @app.get("/stk", response_class=HTMLResponse)
    async def staking_calculator(request: Request):
        """스테이킹 계산기 페이지"""
        return templates.TemplateResponse("features/staking_calculator.html", {"request": request})
    
    @app.get("/bithumb-test", response_class=HTMLResponse)
    async def bithumb_test_page(request: Request):
        """빗썸 API 테스트 페이지"""
        response = templates.TemplateResponse("features/bithumb_test.html", {"request": request})
        # Google 크롤러가 인덱싱하지 않도록 HTTP 헤더 추가
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response
    
    @app.get("/bithumb-guide", response_class=HTMLResponse)
    async def bithumb_guide_page(request: Request):
        """빗썸 API 가이드 페이지"""
        return templates.TemplateResponse("features/bithumb_guide.html", {"request": request})
    
    @app.get("/compliance", response_class=HTMLResponse)
    async def compliance_page(request: Request):
        """컴플라이언스 페이지"""
        return templates.TemplateResponse("features/compliance.html", {"request": request})
    
    @app.get("/privacy-policy", response_class=HTMLResponse)
    async def privacy_policy_page(request: Request):
        """개인정보처리방침 페이지"""
        return templates.TemplateResponse("legal/privacy_policy.html", {"request": request})
    
    @app.get("/terms-of-service", response_class=HTMLResponse)
    async def terms_of_service_page(request: Request):
        """이용약관 페이지"""
        return templates.TemplateResponse("legal/terms_of_service.html", {"request": request})
    
    @app.get("/contact", response_class=HTMLResponse)
    async def contact_page(request: Request):
        """문의사항 페이지"""
        return templates.TemplateResponse("content/contact.html", {"request": request})
    
    @app.get("/guide", response_class=HTMLResponse)
    async def guide_page(request: Request):
        """사이트 이용가이드 페이지"""
        return templates.TemplateResponse("content/guide.html", {"request": request})
    
    @app.get("/about", response_class=HTMLResponse)
    async def about_page(request: Request):
        """서비스 소개 페이지"""
        return templates.TemplateResponse("content/about.html", {"request": request})
