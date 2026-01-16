import uvicorn
import os
import asyncio
import hmac
import hashlib
import time
import json
import base64
import traceback
import jwt
import uuid
import logging
import sys
import re
import bcrypt
from collections import OrderedDict
from urllib.parse import urlencode, quote
from pathlib import Path

import httpx
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable

from src.services.transaction_service import detect_transaction
from src.services.chain_configs import get_chain_configs
from src.services.admin_service import verify_admin_password, is_admin_authenticated, require_admin_auth
from src.routers.blog import register_blog_routes
from src.routers.admin import register_admin_routes
from src.routers.api import register_api_routes
from src.routers.chat import register_chat_routes
from src.routers.pages import register_pages_routes
from src.routers.utility import register_utility_routes

from chatbot import mongodb_client, get_chatbot_graph, vector_store, config
from chatbot.models import get_default_chat_state

load_dotenv()

# --- 환경 감지 및 설정 ---
ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()
DEBUG_MODE = ENVIRONMENT == "development"
RELOAD_ENABLED = os.getenv("RELOAD", "false").lower() == "true" if DEBUG_MODE else False

if DEBUG_MODE:
    default_log_level = "DEBUG"
else:
    default_log_level = "INFO"

# --- LangSmith 추적 초기화 ---
langsmith_tracing = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
langsmith_project = os.getenv("LANGSMITH_PROJECT", "multi-chain-tx-lookup")
langsmith_endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

langchain_tracing_v2 = os.getenv("LANGCHAIN_TRACING_V2", "")
langchain_api_key = os.getenv("LANGCHAIN_API_KEY", "")

if langsmith_tracing or langchain_tracing_v2.lower() == "true":
    if langchain_api_key:
        api_key = langchain_api_key
        project = os.getenv("LANGCHAIN_PROJECT", langsmith_project)
        endpoint = os.getenv("LANGCHAIN_ENDPOINT", langsmith_endpoint)
    elif langsmith_api_key:
        api_key = langsmith_api_key
        project = langsmith_project
        endpoint = langsmith_endpoint

        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = project
    else:
        api_key = None

    if api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = project

        print("="*60)
        print("LangSmith 추적 활성화됨")
        print(f"  - 프로젝트: {project}")
        print(f"  - 엔드포인트: {endpoint}")
        print("="*60)

        try:
            from langsmith import Client
            client = Client(api_key=api_key, api_url=endpoint)
            print(f"✅ LangSmith 클라이언트 초기화 성공")
        except Exception as e:
            print(f"⚠️ LangSmith 클라이언트 초기화 실패: {e}")
    else:
        print("="*60)
        print("⚠️ LangSmith 추적이 활성화되었지만 API 키가 설정되지 않았습니다.")
        print("="*60)
else:
    print("="*60)
    print("LangSmith 추적 비활성화됨")
    print("="*60)

# --- 로깅 설정 ---
log_level_str = os.getenv("LOG_LEVEL", default_log_level).upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

root_logger = logging.getLogger()
root_logger.setLevel(log_level)

httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)
httpx_logger.propagate = True

for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "uvicorn.asgi",
                    "chatbot", "chatbot.chatbot_graph", "chatbot.mongodb_client", 
                    "chatbot.vector_store", "main"]:
    logger_instance = logging.getLogger(logger_name)
    logger_instance.setLevel(log_level)
    logger_instance.propagate = True
    logger_instance.handlers.clear()

logger = logging.getLogger(__name__)
logger.setLevel(log_level)
logger.propagate = True

uvicorn_error_logger = logging.getLogger("uvicorn.error")
uvicorn_error_logger.setLevel(log_level)
uvicorn_error_logger.propagate = True
uvicorn_error_logger.handlers.clear()

print("="*60)
print(f"로깅 시스템 초기화 완료 - 레벨: {log_level_str}")
print("="*60)
logger.info("="*60)
logger.info(f"로깅 시스템 초기화 완료 - 레벨: {log_level_str}")
logger.info("="*60)

# --- FastAPI 앱 초기화 ---
app = FastAPI(title="Multi-Chain Transaction Lookup", version="1.0.0")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-this-in-production"),
    max_age=86400,
    same_site="lax"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# --- 정적 파일 마운트 ---
static_dir = Path(__file__).parent / "static"
static_dir_abs = static_dir.resolve()

if static_dir_abs.exists():
    try:
        app.mount("/static", StaticFiles(directory=str(static_dir_abs), html=False, check_dir=True), name="static")
        print(f"✅ 정적 파일 디렉토리 마운트 성공: {static_dir_abs}")
        logger.info(f"✅ 정적 파일 디렉토리 마운트 성공: {static_dir_abs}")
    except Exception as e:
        print(f"❌ 정적 파일 디렉토리 마운트 실패: {e}")
        logger.error(f"❌ 정적 파일 디렉토리 마운트 실패: {e}", exc_info=True)
else:
    print(f"❌ 정적 파일 디렉토리를 찾을 수 없습니다: {static_dir_abs}")
    logger.error(f"❌ 정적 파일 디렉토리를 찾을 수 없습니다: {static_dir_abs}")
    alt_static = Path("static").resolve()
    if alt_static.exists():
        try:
            app.mount("/static", StaticFiles(directory=str(alt_static)), name="static")
            print(f"✅ 대체 경로로 정적 파일 마운트 성공: {alt_static}")
            logger.info(f"✅ 대체 경로로 정적 파일 마운트 성공: {alt_static}")
        except Exception as e:
            logger.error(f"❌ 대체 경로 마운트도 실패: {e}")

CHAIN_CONFIGS = get_chain_configs()

# --- Startup Event ---
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 MongoDB 연결 및 로깅 재설정"""
    root = logging.getLogger()
    root.setLevel(log_level)
    
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        root.addHandler(handler)
        logger.info("루트 로거 핸들러 추가됨")

    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.WARNING)
    httpx_logger.propagate = True

    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "chatbot", 
                        "chatbot.chatbot_graph", "chatbot.mongodb_client", "chatbot.vector_store"]:
        lg = logging.getLogger(logger_name)
        lg.setLevel(log_level)
        lg.propagate = True
        lg.handlers.clear()

    logger.info("="*60)
    logger.info("애플리케이션 시작 중... (로깅 설정 확인됨)")
    logger.info(f"현재 로깅 레벨: {log_level_str}")
    logger.info("="*60)

    async def connect_databases():
        try:
            logger.info("MongoDB 연결 시도 중...")
            try:
                connected = await asyncio.wait_for(mongodb_client.connect(), timeout=5.0)
                if connected:
                    default_password = os.getenv("ADMIN_PASSWORD", "admin123")
                    await mongodb_client.initialize_admin_password(default_password)
                    logger.info("✅ MongoDB 연결 성공!")
                else:
                    logger.warning("MongoDB 연결 실패")
            except Exception as e:
                logger.warning(f"MongoDB 연결 실패: {e}")

            logger.info("벡터 DB 연결 시도 중...")
            try:
                vector_connected = await asyncio.wait_for(vector_store.connect(), timeout=5.0)
                if vector_connected:
                    logger.info("✅ 벡터 DB 연결 성공!")
                else:
                    logger.warning("벡터 DB 연결 실패")
            except Exception as e:
                logger.warning(f"벡터 DB 연결 실패: {e}")

        except Exception as e:
            logger.error(f"데이터베이스 연결 중 오류: {e}", exc_info=True)

    asyncio.create_task(connect_databases())

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 MongoDB 연결 해제"""
    logger.info("애플리케이션 종료 중...")
    await mongodb_client.disconnect()
    await vector_store.disconnect()
    logger.info("MongoDB 연결 해제 완료")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

# --- 라우터 등록 ---
register_blog_routes(app, templates)
register_admin_routes(app, templates)
register_api_routes(app, templates)
register_chat_routes(app, templates)
register_pages_routes(app, templates)
register_utility_routes(app)

# --- 페이지 라우트 ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    excluded_chains = ["litecoin", "dogecoin"]
    supported_chains = [{ "name": config["name"], "symbol": config["symbol"] } for key, config in CHAIN_CONFIGS.items() if "name" in config and key not in excluded_chains]
    return templates.TemplateResponse("pages/explorer_ui.html", {"request": request, "supported_chains": supported_chains})

@app.get("/stk", response_class=HTMLResponse)
async def staking_calculator(request: Request):
    return templates.TemplateResponse("features/staking_calculator.html", {"request": request})

@app.get("/api/tx/{txid}")
async def get_transaction(txid: str):
    results = await detect_transaction(txid)
    if results:
        return JSONResponse(content={"found": True, "results": results})
    else:
        return JSONResponse(content={"found": False, "message": "Transaction not found on supported chains."})

@app.get("/api/chains")
async def get_chains():
    configs = get_chain_configs()
    supported_chains = []
    for key, config in configs.items():
        if key == "avalanche_henesys_subnet":
            continue
        else:
            supported_chains.append({
                "name": config["name"], 
                "symbol": config["symbol"],
                "explorer": config["explorer"].replace("/tx/", "/")
            })
    return JSONResponse(content={"supportedChains": supported_chains})

# --- 기타 페이지 ---
@app.get("/bithumb-test")
async def bithumb_test_page(request: Request):
    return templates.TemplateResponse("features/bithumb_test.html", {"request": request})

@app.get("/bithumb-guide")
async def bithumb_guide_page(request: Request):
    return templates.TemplateResponse("features/bithumb_guide.html", {"request": request})

@app.get("/compliance", response_class=HTMLResponse)
async def bithumb_compliance_page(request: Request):
    return templates.TemplateResponse("features/compliance.html", {"request": request})

@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy_page(request: Request):
    return templates.TemplateResponse("legal/privacy_policy.html", {"request": request})

@app.get("/terms-of-service", response_class=HTMLResponse)
async def terms_of_service_page(request: Request):
    return templates.TemplateResponse("legal/terms_of_service.html", {"request": request})

@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse("content/contact.html", {"request": request})

@app.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    return templates.TemplateResponse("content/guide.html", {"request": request})

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse("content/about.html", {"request": request})

# --- Admin 관련 ---
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    if is_admin_authenticated(request):
        return RedirectResponse(url="/admin/inquiries", status_code=303)
    redirect_url = request.query_params.get("redirect", "/admin/inquiries")
    return templates.TemplateResponse("admin/admin_login.html", {"request": request, "redirect_url": redirect_url})

@app.post("/admin/login")
async def admin_login_submit(request: Request):
    try:
        data = await request.json()
        password = data.get("password", "")

        if await verify_admin_password(password):
            request.session["admin_authenticated"] = True
            redirect_url = data.get("redirect_url", "/admin/inquiries")
            logger.info(f"관리자 로그인 성공: {request.client.host if request.client else 'unknown'}")
            return JSONResponse(content={"success": True, "redirect_url": redirect_url})
        else:
            logger.warning(f"관리자 로그인 실패: {request.client.host if request.client else 'unknown'}")
            return JSONResponse(status_code=401, content={"success": False, "message": "비밀번호가 일치하지 않습니다."})
    except Exception as e:
        logger.error(f"관리자 로그인 API 오류: {e}", exc_info=True)

@app.post("/admin/logout")
async def admin_logout(request: Request):
    request.session.clear()
    return JSONResponse(content={"success": True, "message": "로그아웃되었습니다."})

@app.get("/admin/inquiries", response_class=HTMLResponse)
async def admin_inquiries_page(request: Request):
    redirect = await require_admin_auth(request)
    if redirect:
        return redirect
    return templates.TemplateResponse("admin/admin_inquiries.html", {"request": request})

@app.get("/admin/inquiries/stats", response_class=HTMLResponse)
async def admin_inquiries_stats_page(request: Request):
    redirect = await require_admin_auth(request)
    if redirect:
        return redirect
    return templates.TemplateResponse("admin/admin_stats.html", {"request": request})

@app.get("/admin/chat/stats", response_class=HTMLResponse)
async def admin_chat_stats_page(request: Request):
    redirect = await require_admin_auth(request)
    if redirect:
        return redirect
    return templates.TemplateResponse("admin/admin_chat_stats.html", {"request": request})

# --- Contact API ---
@app.post("/api/contact")
async def submit_contact(request: Request):
    try:
        data = await request.json()
        email = data.get("email", "").strip()
        category = data.get("category", "").strip()
        subject = data.get("subject", "").strip()
        message = data.get("message", "").strip()

        if not email or "@" not in email:
            return JSONResponse(status_code=400, content={"success": False, "message": "올바른 이메일 형식을 입력해주세요."})
        if not category:
            return JSONResponse(status_code=400, content={"success": False, "message": "문의 유형을 선택해주세요."})
        if not subject:
            return JSONResponse(status_code=400, content={"success": False, "message": "제목을 입력해주세요."})
        if not message:
            return JSONResponse(status_code=400, content={"success": False, "message": "내용을 입력해주세요."})

        result = await mongodb_client.save_inquiry(
            email=email, category=category, subject=subject, message=message,
            metadata={"user_agent": request.headers.get("user-agent", ""), "ip_address": request.client.host if request.client else None}
        )

        if result:
            logger.info(f"문의사항 저장 성공: {email} - {subject}")
            return JSONResponse(content={"success": True, "message": "문의사항이 성공적으로 전송되었습니다."})
        else:
            logger.error(f"문의사항 저장 실패: {email} - {subject}")
            return JSONResponse(status_code=500, content={"success": False, "message": "문의사항 전송에 실패했습니다."})
    except Exception as e:
        logger.error(f"문의사항 API 오류: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "message": "서버 오류가 발생했습니다."})

# --- Admin API ---
@app.get("/api/admin/inquiries")
async def get_inquiries(request: Request):
    try:
        if not is_admin_authenticated(request):
            return JSONResponse(status_code=401, content={"success": False, "message": "인증이 필요합니다."})

        status = request.query_params.get("status", None)
        limit = int(request.query_params.get("limit", 100))
        skip = int(request.query_params.get("skip", 0))

        inquiries = await mongodb_client.get_inquiries(limit=limit, skip=skip, status=status)
        return JSONResponse(content={"success": True, "inquiries": inquiries})
    except Exception as e:
        logger.error(f"문의사항 조회 API 오류: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "message": "서버 오류가 발생했습니다."})

@app.get("/api/admin/inquiries/stats")
async def get_inquiry_stats(request: Request):
    try:
        if not is_admin_authenticated(request):
            return JSONResponse(status_code=401, content={"success": False, "message": "인증이 필요합니다."})

        total = await mongodb_client.get_inquiry_count()
        pending = await mongodb_client.get_inquiry_count(status="pending")
        replied = await mongodb_client.get_inquiry_count(status="replied")
        closed = await mongodb_client.get_inquiry_count(status="closed")
        return JSONResponse(content={"success": True, "total": total, "pending": pending, "replied": replied, "closed": closed})
    except Exception as e:
        logger.error(f"문의사항 통계 API 오류: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "message": "서버 오류가 발생했습니다."})

@app.get("/api/admin/inquiries/detailed-stats")
async def get_detailed_inquiry_stats(request: Request):
    try:
        if not is_admin_authenticated(request):
            return JSONResponse(status_code=401, content={"success": False, "message": "인증이 필요합니다."})
        stats = await mongodb_client.get_inquiry_statistics()
        return JSONResponse(content={"success": True, "stats": stats})
    except Exception as e:
        logger.error(f"문의사항 상세 통계 API 오류: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "message": "서버 오류가 발생했습니다."})

@app.get("/api/admin/chat/stats")
async def get_chat_stats(request: Request):
    try:
        if not is_admin_authenticated(request):
            return JSONResponse(status_code=401, content={"success": False, "message": "인증이 필요합니다."})
        stats = await mongodb_client.get_chat_statistics()
        return JSONResponse(content={"success": True, "stats": stats})
    except Exception as e:
        logger.error(f"채팅 상세 통계 API 오류: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "message": "서버 오류가 발생했습니다."})

@app.get("/api/admin/chat/content-stats")
async def get_chat_content_stats(request: Request):
    try:
        if not is_admin_authenticated(request):
            return JSONResponse(status_code=401, content={"success": False, "message": "인증이 필요합니다."})
        use_ai = request.query_params.get("use_ai", "true").lower() == "true"
        stats = await mongodb_client.get_chat_content_statistics(use_ai_analysis=use_ai)
        return JSONResponse(content={"success": True, "stats": stats, "ai_analysis_enabled": use_ai})
    except Exception as e:
        logger.error(f"채팅 내용 통계 API 오류: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "message": "서버 오류가 발생했습니다."})

@app.post("/api/admin/change-password")
async def change_admin_password(request: Request):
    try:
        if not is_admin_authenticated(request):
            return JSONResponse(status_code=401, content={"success": False, "message": "인증이 필요합니다."})

        data = await request.json()
        current_password = data.get("current_password", "")
        new_password = data.get("new_password", "")
        confirm_password = data.get("confirm_password", "")

        if not current_password or not new_password or not confirm_password:
            return JSONResponse(status_code=400, content={"success": False, "message": "모든 필드를 입력해주세요."})
        if new_password != confirm_password:
            return JSONResponse(status_code=400, content={"success": False, "message": "새 비밀번호가 일치하지 않습니다."})
        if len(new_password) < 6:
            return JSONResponse(status_code=400, content={"success": False, "message": "비밀번호는 최소 6자 이상이어야 합니다."})

        if not await verify_admin_password(current_password):
            return JSONResponse(status_code=401, content={"success": False, "message": "현재 비밀번호가 일치하지 않습니다."})

        new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        success = await mongodb_client.set_admin_password_hash(new_password_hash)

        if success:
            logger.info(f"관리자 비밀번호가 변경되었습니다: {request.client.host if request.client else 'unknown'}")
            return JSONResponse(content={"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."})
        else:
            return JSONResponse(status_code=500, content={"success": False, "message": "비밀번호 변경에 실패했습니다."})
    except Exception as e:
        logger.error(f"비밀번호 변경 오류: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "message": "서버 오류가 발생했습니다."})

@app.post("/api/admin/inquiries/{inquiry_id}/status")
async def update_inquiry_status(inquiry_id: str, request: Request):
    try:
        if not is_admin_authenticated(request):
            return JSONResponse(status_code=401, content={"success": False, "message": "인증이 필요합니다."})

        data = await request.json()
        status = data.get("status", "")
        if status not in ["pending", "replied", "closed"]:
            return JSONResponse(status_code=400, content={"success": False, "message": "유효하지 않은 상태입니다."})

        result = await mongodb_client.update_inquiry_status(inquiry_id, status)
        if result:
            logger.info(f"문의사항 상태 업데이트 성공: {inquiry_id} -> {status}")
            return JSONResponse(content={"success": True, "message": "상태가 업데이트되었습니다."})
        else:
            return JSONResponse(status_code=404, content={"success": False, "message": "문의사항을 찾을 수 없습니다."})
    except Exception as e:
        logger.error(f"문의사항 상태 업데이트 API 오류: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "message": "서버 오류가 발생했습니다."})

# --- 디버그용 API ---
@app.get("/api/debug/static-files")
async def debug_static_files():
    try:
        static_dir = Path(__file__).parent / "static"
        static_dir_abs = static_dir.resolve()
        result = {"static_dir": str(static_dir_abs), "exists": static_dir_abs.exists(), "files": {}}
        if static_dir_abs.exists():
            css_files = list(static_dir_abs.glob("css/*.css"))
            result["files"]["css"] = [{"name": f.name, "path": str(f.relative_to(static_dir_abs)), "exists": f.exists(), "size": f.stat().st_size if f.exists() else 0} for f in css_files]
            js_files = list(static_dir_abs.glob("js/*.js"))
            result["files"]["js"] = [{"name": f.name, "path": str(f.relative_to(static_dir_abs)), "exists": f.exists(), "size": f.stat().st_size if f.exists() else 0} for f in js_files]
            other_files = []
            for ext in ["*.txt", "*.xml", "*.json"]:
                other_files.extend(static_dir_abs.glob(ext))
            result["files"]["other"] = [{"name": f.name, "path": str(f.relative_to(static_dir_abs)), "exists": f.exists(), "size": f.stat().st_size if f.exists() else 0} for f in other_files]
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": str(e.__traceback__)})

@app.get("/robots.txt")
async def robots_txt():
    robots_path = "static/robots.txt"
    if os.path.exists(robots_path):
        return FileResponse(robots_path, media_type="text/plain")
    else:
        return Response(content="User-agent: *\nAllow: /", media_type="text/plain")

@app.get("/sitemap.xml")
async def sitemap_xml():
    sitemap_path = "static/sitemap.xml"
    if os.path.exists(sitemap_path):
        return FileResponse(sitemap_path, media_type="application/xml")
    else:
        return Response(content="<?xml version='1.0' encoding='UTF-8'?><urlset></urlset>", media_type="application/xml")

# --- Bithumb API Test ---
@app.post("/api/bithumb/test")
async def test_bithumb_api(request: Request):
    try:
        data = await request.json()
        api_version = data.get("apiVersion")
        api_key = os.getenv("BITHUMB_API_KEY")
        secret_key = os.getenv("BITHUMB_SECRET_KEY")
        endpoint = data.get("selectedEndpoint")
        method = data.get("method", "POST")

        if not api_key or not secret_key:
            return {"success": False, "requestUrl": "", "requestHeaders": {}, "requestBody": "", "result": {"error": "API Key, Secret Key를 환경변수에 설정하세요."}}

        base_url = "https://api.bithumb.com/"
        endpoint_url = base_url + endpoint
        params = data.get("params", {}) or {}

        if not endpoint:
            return {"success": False, "result": {"error": "엔드포인트가 선택되지 않았습니다."}}

        if api_version == "v1":
            nonce = str(int(time.time() * 1000))
            req_params = OrderedDict()
            req_params['endpoint'] = f'/{endpoint}'
            if params:
                req_params.update(params)
            
            request_body_string = urlencode(req_params)
            data_to_sign = f"/{endpoint}\0{request_body_string}\0{nonce}"
            signature = hmac.new(secret_key.encode('utf-8'), data_to_sign.encode('utf-8'), hashlib.sha512)
            api_sign = base64.b64encode(signature.digest()).decode('utf-8')

            headers = {
                "Api-Key": api_key, "Api-Nonce": nonce, "Api-Sign": api_sign,
                "Content-Type": "application/x-www-form-urlencoded", "api-client-type": "0"
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint_url, headers=headers, content=request_body_string)
            return await handle_response(response, endpoint_url, headers, request_body_string)

        elif api_version == "v2":
            print("=== 빗썸 공식 방식으로 JWT 토큰 생성 ===")
            payload = {'access_key': api_key, 'nonce': str(uuid.uuid4()), 'timestamp': round(time.time() * 1000)}
            
            withdraw_request_body = None
            if endpoint == 'v1/accounts':
                params = {}
            elif endpoint == 'v1/withdraws/coin' and params:
                requestBody = dict(**params)
                query_parts = [f"{key}={value}" for key, value in requestBody.items()]
                raw_query = "&".join(query_parts)
                query_hash = hashlib.sha512(raw_query.encode('utf-8')).hexdigest()
                payload['query_hash'] = query_hash
                payload['query_hash_alg'] = 'SHA512'
                withdraw_request_body = requestBody

            try:
                jwt_token_raw = jwt.encode(payload, secret_key)
                jwt_token = jwt_token_raw if isinstance(jwt_token_raw, str) else jwt_token_raw.decode('utf-8')
                authorization_token = f"Bearer {jwt_token}"
            except Exception as e:
                return {"success": False, "result": {"error": f"JWT 토큰 생성 실패: {str(e)}"}}

            headers = {'Authorization': authorization_token}
            if method == 'POST':
                headers['Content-Type'] = 'application/json'

            try:
                async with httpx.AsyncClient() as client:
                    if method == "GET":
                        response = await client.get(endpoint_url, headers=headers)
                    elif method == "DELETE":
                        response = await client.delete(endpoint_url, headers=headers)
                    else: # POST
                        if endpoint == 'v1/withdraws/coin' and withdraw_request_body:
                            json_data = json.dumps(withdraw_request_body)
                        else:
                            json_data = json.dumps(params or {})
                        response = await client.post(endpoint_url, headers=headers, data=json_data)
            except Exception as err:
                return {"success": False, "result": {"error": f"API 호출 실패: {str(err)}"}}

            display_body = json.dumps(params, ensure_ascii=False) if method in ['POST', 'PUT', 'DELETE'] and params else params
            
            if response.status_code == 401:
                return {
                    "success": False, "requestUrl": endpoint_url, "requestHeaders": headers, "requestBody": display_body,
                    "result": {"error": "JWT 토큰 검증 실패.", "status_code": response.status_code, "response_text": response.text}
                }
            return await handle_response(response, endpoint_url, headers, display_body)
        else:
            return {"success": False, "result": {"error": "지원하지 않는 API 버전입니다."}}
    except Exception as e:
        return {"success": False, "requestUrl": "", "requestHeaders": {}, "result": {"error": str(e), "traceback": traceback.format_exc()}}

async def handle_response(response, url, headers, body):
    request_body_display = body
    if isinstance(body, (dict, list)):
        try:
            request_body_display = json.dumps(body, indent=2, ensure_ascii=False)
        except TypeError:
            request_body_display = str(body)
    try:
        result = response.json()
    except json.JSONDecodeError:
        return {"success": False, "requestUrl": url, "requestHeaders": headers, "requestBody": request_body_display, "result": {"error": "JSON 형식 아님", "raw": response.text}}

    success = False
    if isinstance(result, dict) and result.get("status") == "0000":
        success = True
    elif isinstance(result, list) and response.status_code == 200:
        success = True

    return {"success": success, "requestUrl": url, "requestHeaders": headers, "requestBody": request_body_display, "result": result}

# --- 챗봇 API ---
@app.post("/api/chat")
@traceable(name="chat_endpoint", run_type="chain")
async def chat(request: Request):
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        session_id = data.get("session_id", str(uuid.uuid4()))
        if not message:
            return JSONResponse(content={"error": "메시지를 입력해주세요."}, status_code=400)
        
        if not os.getenv("OPENAI_API_KEY"):
            return JSONResponse(content={"error": "OpenAI API 키 설정 필요."}, status_code=500)

        chatbot_logger = logging.getLogger("chatbot.chatbot_graph")
        chatbot_logger.propagate = True
        chatbot_logger.handlers.clear()
        chatbot_logger.setLevel(log_level)

        logger.info(f"채팅 요청 수신: 세션={session_id}, 메시지={message[:50]}...")
        try:
            graph = get_chatbot_graph()
        except Exception as graph_error:
            logger.error(f"챗봇 초기화 실패: {graph_error}", exc_info=True)
            return JSONResponse(content={"error": f"챗봇 초기화 실패: {str(graph_error)}"}, status_code=500)

        history_messages = []
        try:
            history = await mongodb_client.get_conversation_history(session_id, limit=10)
            for msg in history:
                if msg.get("role") == "user":
                    history_messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    history_messages.append(AIMessage(content=msg.get("content", "")))
        except Exception as e:
            logger.warning(f"대화 기록 조회 실패: {e}")

        initial_state = get_default_chat_state(session_id=session_id, messages=history_messages + [HumanMessage(content=message)])
        result = await graph.ainvoke(initial_state)

        if result.get("messages"):
            ai_message = result["messages"][-1]
            response_text = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
        else:
            response_text = "응답을 생성할 수 없습니다."

        debug_param = data.get("debug", False)
        db_search_results = result.get("db_search_results", [])
        similarity_scores = []
        
        if db_search_results:
            for i, result_item in enumerate(db_search_results):
                score = result_item.get("score", 0.0)
                similarity_scores.append({
                    "rank": i + 1, "score": float(score), "score_formatted": f"{score:.4f}",
                    "text_preview": result_item.get("text", "")[:100] + "...",
                    "source": result_item.get("source", ""),
                    "threshold": float(config.SIMILARITY_THRESHOLD),
                    "passed": float(score) > config.SIMILARITY_THRESHOLD
                })

        response_data = {"response": response_text, "session_id": session_id}
        if debug_param:
            response_data["debug"] = {
                "similarity_scores": similarity_scores,
                "needs_deep_research": result.get("needs_deep_research", None),
                "threshold": float(config.SIMILARITY_THRESHOLD)
            }
        return JSONResponse(content=response_data)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"error": f"처리 중 오류: {str(e)}"}, status_code=500)

@app.post("/api/crawl")
async def crawl_website(request: Request):
    try:
        data = await request.json()
        url = data.get("url", "")
        if not url:
            return JSONResponse(content={"error": "URL을 입력해주세요."}, status_code=400)
        asyncio.create_task(vector_store.crawl_and_store(url))
        return JSONResponse(content={"message": "크롤링 시작됨", "url": url})
    except Exception as e:
        return JSONResponse(content={"error": f"크롤링 실패: {str(e)}"}, status_code=500)

if __name__ == "__main__":
    logger.info("="*60)
    logger.info(f"환경: {ENVIRONMENT.upper()}, 디버그: {DEBUG_MODE}, 리로드: {RELOAD_ENABLED}")
    logger.info("="*60)

    ssl_keyfile = os.getenv("SSL_KEY_PATH")
    ssl_certfile = os.getenv("SSL_CERT_PATH")
    if ssl_keyfile and ssl_certfile:
        logger.warning("⚠️ SSL 설정이 감지되었습니다.")

    log_level_uvicorn = os.getenv("LOG_LEVEL", default_log_level.lower()).lower()

    def setup_logging():
        root = logging.getLogger()
        root.setLevel(log_level)
        if not root.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            root.addHandler(handler)
        for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "chatbot"]:
            lg = logging.getLogger(logger_name)
            lg.setLevel(log_level)
            lg.propagate = True
            lg.handlers.clear()

    import uvicorn.config
    uvicorn_log_config = {
        "version": 1, "disable_existing_loggers": False,
        "formatters": {
            "default": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s", "datefmt": "%Y-%m-%d %H:%M:%S"},
            "access": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s", "datefmt": "%Y-%m-%d %H:%M:%S"},
        },
        "handlers": {
            "default": {"formatter": "default", "class": "logging.StreamHandler", "stream": "ext://sys.stdout"},
            "access": {"formatter": "access", "class": "logging.StreamHandler", "stream": "ext://sys.stdout"},
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": log_level_str, "propagate": True},
            "uvicorn.error": {"handlers": ["default"], "level": log_level_str, "propagate": True},
            "uvicorn.access": {"handlers": ["access"], "level": log_level_str, "propagate": True},
        },
        "root": {"level": log_level_str, "handlers": ["default"]},
    }

    host = "127.0.0.1" if DEBUG_MODE else "0.0.0.0"

    if ssl_keyfile and ssl_certfile:
        logger.info("SSL 모드로 서버 시작 (포트 443)")
        uvicorn.run("main:app", host=host, port=443, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile, log_level=log_level_uvicorn, log_config=uvicorn_log_config, use_colors=False, access_log=True, reload=RELOAD_ENABLED)
    else:
        logger.info(f"일반 모드로 서버 시작 (포트 8000, 호스트: {host})")
        uvicorn.run("main:app", host=host, port=8000, log_level=log_level_uvicorn, log_config=uvicorn_log_config, use_colors=False, access_log=True, reload=RELOAD_ENABLED)