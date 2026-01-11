from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from src.services.transaction_service import detect_transaction
from src.services.chain_configs import get_chain_configs
from chatbot import mongodb_client, get_chatbot_graph, vector_store, config
from chatbot.models import get_default_chat_state
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable
import uvicorn
import os
import asyncio
from dotenv import load_dotenv
import hmac
import hashlib
import time
import json
from urllib.parse import urlencode, quote
import httpx
import base64
import traceback
import jwt
import uuid
from collections import OrderedDict
import logging
import sys
import re

load_dotenv()

# LangSmith 추적 초기화 (환경 변수 확인 및 로깅)
langsmith_tracing = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
langsmith_project = os.getenv("LANGSMITH_PROJECT", "multi-chain-tx-lookup")
langsmith_endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

# LangChain 환경 변수 직접 확인 (우선순위)
langchain_tracing_v2 = os.getenv("LANGCHAIN_TRACING_V2", "")
langchain_api_key = os.getenv("LANGCHAIN_API_KEY", "")

# LangSmith 또는 LangChain 환경 변수 중 하나라도 설정되어 있으면 활성화
if langsmith_tracing or langchain_tracing_v2.lower() == "true":
    # LangChain 환경 변수 우선 사용, 없으면 LangSmith 환경 변수 사용
    if langchain_api_key:
        api_key = langchain_api_key
        project = os.getenv("LANGCHAIN_PROJECT", langsmith_project)
        endpoint = os.getenv("LANGCHAIN_ENDPOINT", langsmith_endpoint)
    elif langsmith_api_key:
        api_key = langsmith_api_key
        project = langsmith_project
        endpoint = langsmith_endpoint
        # LangChain 환경 변수로 설정
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = project
    else:
        api_key = None
    
    if api_key:
        # 환경 변수 강제 설정 (재확인)
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = project
        
        # LangSmith 클라이언트 초기화 확인을 위한 로깅
        print("="*60)
        print("LangSmith 추적 활성화됨")
        print(f"  - 프로젝트: {project}")
        print(f"  - 엔드포인트: {endpoint}")
        print(f"  - LANGCHAIN_TRACING_V2: {os.getenv('LANGCHAIN_TRACING_V2')}")
        print(f"  - LANGCHAIN_PROJECT: {os.getenv('LANGCHAIN_PROJECT')}")
        print(f"  - API 키: {api_key[:20]}... (처음 20자)")
        print("="*60)
        
        # LangSmith 초기화 확인
        try:
            from langsmith import Client
            client = Client(api_key=api_key, api_url=endpoint)
            print(f"✅ LangSmith 클라이언트 초기화 성공")
        except Exception as e:
            print(f"⚠️ LangSmith 클라이언트 초기화 실패: {e}")
    else:
        print("="*60)
        print("⚠️ LangSmith 추적이 활성화되었지만 API 키가 설정되지 않았습니다.")
        print("   LANGSMITH_API_KEY 또는 LANGCHAIN_API_KEY를 설정해주세요.")
        print("="*60)
else:
    print("="*60)
    print("LangSmith 추적 비활성화됨 (LANGSMITH_TRACING=false 또는 미설정)")
    print("="*60)

# 로깅 설정 (가장 먼저 실행) - uvicorn 시작 전에 강제 적용
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

# logging.basicConfig 사용 (force=True로 기존 설정 덮어쓰기)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True  # 기존 설정 덮어쓰기
)

# 루트 로거 설정 강화
root_logger = logging.getLogger()
root_logger.setLevel(log_level)

# 모든 하위 로거 설정 (propagate=True로 루트 로거 사용)
for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "uvicorn.asgi",
                    "chatbot", "chatbot.chatbot_graph", "chatbot.mongodb_client", 
                    "chatbot.vector_store", "main"]:
    logger_instance = logging.getLogger(logger_name)
    logger_instance.setLevel(log_level)
    logger_instance.propagate = True  # 루트 로거로 전파
    # 기존 핸들러 제거 (uvicorn이 추가할 수 있는 것들)
    logger_instance.handlers.clear()

# 애플리케이션 로거
logger = logging.getLogger(__name__)
logger.setLevel(log_level)
logger.propagate = True

# uvicorn 로거도 명시적으로 설정
uvicorn_error_logger = logging.getLogger("uvicorn.error")
uvicorn_error_logger.setLevel(log_level)
uvicorn_error_logger.propagate = True
uvicorn_error_logger.handlers.clear()

uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.setLevel(log_level)
uvicorn_access_logger.propagate = True
uvicorn_access_logger.handlers.clear()

# 로깅 초기화 확인 메시지 (즉시 출력)
print("="*60)
print(f"로깅 시스템 초기화 완료 - 레벨: {log_level_str}")
print("="*60)
logger.info("="*60)
logger.info(f"로깅 시스템 초기화 완료 - 레벨: {log_level_str}")
logger.info("="*60)

app = FastAPI(title="Multi-Chain Transaction Lookup", version="1.0.0")

# 세션 미들웨어 추가 (관리자 인증용)
# AWS 환경에서는 HTTPS를 사용하므로 secure 쿠키 필요
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-this-in-production"),
    max_age=86400,  # 24시간
    same_site="lax"
)

# CORS 설정 추가 (AWS 배포용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# Static 파일 디렉토리 마운트
import os
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

CHAIN_CONFIGS = get_chain_configs()

# MongoDB 연결 초기화
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 MongoDB 연결 및 로깅 재설정"""
    # uvicorn 시작 후에도 로깅 설정 유지 및 확인
    root = logging.getLogger()
    root.setLevel(log_level)
    
    # 핸들러 확인 및 추가
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)
        logger.info("루트 로거 핸들러 추가됨")
    
    # 하위 로거 재설정 (중요: chatbot 로거들)
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "chatbot", 
                        "chatbot.chatbot_graph", "chatbot.mongodb_client", "chatbot.vector_store"]:
        lg = logging.getLogger(logger_name)
        lg.setLevel(log_level)
        lg.propagate = True  # 루트 로거로 전파
        lg.handlers.clear()  # 중복 핸들러 제거
    
    # 로깅 상태 확인
    logger.info("="*60)
    logger.info("애플리케이션 시작 중... (로깅 설정 확인됨)")
    logger.info(f"현재 로깅 레벨: {log_level_str}")
    logger.info(f"루트 로거 핸들러 개수: {len(root.handlers)}")
    
    # chatbot 로거 상태 확인
    chatbot_graph_logger = logging.getLogger("chatbot.chatbot_graph")
    logger.info(f"chatbot.chatbot_graph 로거 - 핸들러: {len(chatbot_graph_logger.handlers)}, propagate: {chatbot_graph_logger.propagate}, 레벨: {chatbot_graph_logger.level}")
    
    logger.info("="*60)
    
    # MongoDB 및 벡터 DB 연결을 별도 태스크로 실행하여 서버 시작을 블로킹하지 않음
    async def connect_databases():
        """데이터베이스 연결을 비동기로 실행 (서버 시작을 블로킹하지 않음)"""
        try:
            # 대화 기록용 MongoDB 연결
            logger.info("MongoDB 연결 시도 중...")
            try:
                # 타임아웃 설정 (5초)
                connected = await asyncio.wait_for(mongodb_client.connect(), timeout=5.0)
                if not connected:
                    logger.warning("MongoDB 연결 실패 - 챗봇 기능이 제한될 수 있습니다.")
                else:
                    logger.info("✅ MongoDB 연결 성공!")
            except asyncio.TimeoutError:
                logger.warning("MongoDB 연결 타임아웃 (5초) - 챗봇 기능이 제한될 수 있습니다.")
            except asyncio.CancelledError:
                logger.warning("MongoDB 연결이 취소되었습니다 - 챗봇 기능이 제한될 수 있습니다.")
            except Exception as e:
                logger.warning(f"MongoDB 연결 실패: {e} - 챗봇 기능이 제한될 수 있습니다.")
            
            # 벡터 DB 연결
            logger.info("벡터 DB 연결 시도 중...")
            try:
                # 타임아웃 설정 (5초)
                vector_connected = await asyncio.wait_for(vector_store.connect(), timeout=5.0)
                if not vector_connected:
                    logger.warning("벡터 DB 연결 실패 - 벡터 검색 기능이 제한될 수 있습니다.")
                else:
                    logger.info("✅ 벡터 DB 연결 성공!")
            except asyncio.TimeoutError:
                logger.warning("벡터 DB 연결 타임아웃 (5초) - 벡터 검색 기능이 제한될 수 있습니다.")
            except asyncio.CancelledError:
                logger.warning("벡터 DB 연결이 취소되었습니다 - 벡터 검색 기능이 제한될 수 있습니다.")
            except Exception as e:
                logger.warning(f"벡터 DB 연결 실패: {e} - 벡터 검색 기능이 제한될 수 있습니다.")
                
        except Exception as e:
            logger.error(f"데이터베이스 연결 시도 중 예상치 못한 오류 발생: {e}", exc_info=True)
            logger.warning("챗봇 기능은 제한될 수 있지만, 서버는 계속 실행됩니다.")
    
    # 백그라운드 태스크로 실행 (서버 시작을 블로킹하지 않음)
    asyncio.create_task(connect_databases())

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 MongoDB 연결 해제"""
    logger.info("애플리케이션 종료 중...")
    await mongodb_client.disconnect()
    await vector_store.disconnect()
    logger.info("MongoDB 연결 해제 완료")

# 헬스체크 엔드포인트 추가 (AWS ALB/ELB용)
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    excluded_chains = ["litecoin", "dogecoin"]
    supported_chains = [{ "name": config["name"], "symbol": config["symbol"] } for key, config in CHAIN_CONFIGS.items() if "name" in config and key not in excluded_chains]
    return templates.TemplateResponse("explorer_ui.html", {"request": request, "supported_chains": supported_chains})

@app.get("/stk", response_class=HTMLResponse)
async def staking_calculator(request: Request):
    return templates.TemplateResponse("staking_calculator.html", {"request": request})

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

@app.get("/bithumb-test")
async def bithumb_test_page(request: Request):
    return templates.TemplateResponse("bithumb_test.html", {"request": request})

@app.get("/bithumb-guide")
async def bithumb_guide_page(request: Request):
    """빗썸 API 가이드 페이지"""
    return templates.TemplateResponse("bithumb_guide.html", {"request": request})

@app.get("/compliance", response_class=HTMLResponse)
async def bithumb_compliance_page(request: Request):
    return templates.TemplateResponse("compliance.html", {"request": request})

@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy_page(request: Request):
    """개인정보처리방침 페이지"""
    return templates.TemplateResponse("privacy_policy.html", {"request": request})

@app.get("/terms-of-service", response_class=HTMLResponse)
async def terms_of_service_page(request: Request):
    """이용약관 페이지"""
    return templates.TemplateResponse("terms_of_service.html", {"request": request})

@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    """문의사항 페이지"""
    return templates.TemplateResponse("contact.html", {"request": request})

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """관리자 로그인 페이지"""
    # 이미 로그인되어 있으면 관리자 페이지로 리다이렉트
    if is_admin_authenticated(request):
        return RedirectResponse(url="/admin/inquiries", status_code=303)
    
    redirect_url = request.query_params.get("redirect", "/admin/inquiries")
    return templates.TemplateResponse("admin_login.html", {"request": request, "redirect_url": redirect_url})

@app.post("/admin/login")
async def admin_login(request: Request):
    """관리자 로그인 API"""
    try:
        data = await request.json()
        password = data.get("password", "")
        
        if verify_admin_password(password):
            request.session["admin_authenticated"] = True
            redirect_url = data.get("redirect_url", "/admin/inquiries")
            logger.info(f"관리자 로그인 성공: {request.client.host if request.client else 'unknown'}")
            
            # 세션 쿠키 설정 (AWS 환경 대응)
            response = JSONResponse(
                content={"success": True, "redirect_url": redirect_url}
            )
            # 세션 쿠키가 제대로 설정되도록 명시적으로 설정
            # SessionMiddleware가 자동으로 처리하지만, 명시적으로 설정
            return response
        else:
            logger.warning(f"관리자 로그인 실패: {request.client.host if request.client else 'unknown'}")
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "비밀번호가 일치하지 않습니다."}
            )
    except Exception as e:
        logger.error(f"관리자 로그인 API 오류: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "서버 오류가 발생했습니다."}
        )

@app.post("/admin/logout")
async def admin_logout(request: Request):
    """관리자 로그아웃 API"""
    request.session.clear()
    return JSONResponse(
        content={"success": True, "message": "로그아웃되었습니다."}
    )

@app.get("/admin/inquiries", response_class=HTMLResponse)
async def admin_inquiries_page(request: Request):
    """문의사항 관리 페이지"""
    # 인증 확인
    redirect = await require_admin_auth(request)
    if redirect:
        return redirect
    
    return templates.TemplateResponse("admin_inquiries.html", {"request": request})

@app.post("/api/contact")
async def submit_contact(request: Request):
    """문의사항 제출 API"""
    try:
        data = await request.json()
        
        email = data.get("email", "").strip()
        category = data.get("category", "").strip()
        subject = data.get("subject", "").strip()
        message = data.get("message", "").strip()
        
        # 유효성 검사
        if not email:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "이메일을 입력해주세요."}
            )
        
        if not email or "@" not in email:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "올바른 이메일 형식을 입력해주세요."}
            )
        
        if not category:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "문의 유형을 선택해주세요."}
            )
        
        if not subject:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "제목을 입력해주세요."}
            )
        
        if not message:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "내용을 입력해주세요."}
            )
        
        # MongoDB에 저장
        result = await mongodb_client.save_inquiry(
            email=email,
            category=category,
            subject=subject,
            message=message,
            metadata={
                "user_agent": request.headers.get("user-agent", ""),
                "ip_address": request.client.host if request.client else None
            }
        )
        
        if result:
            logger.info(f"문의사항 저장 성공: {email} - {subject}")
            return JSONResponse(
                content={"success": True, "message": "문의사항이 성공적으로 전송되었습니다."}
            )
        else:
            logger.error(f"문의사항 저장 실패: {email} - {subject}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "문의사항 전송에 실패했습니다. 다시 시도해주세요."}
            )
            
    except Exception as e:
        logger.error(f"문의사항 API 오류: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "서버 오류가 발생했습니다. 나중에 다시 시도해주세요."}
        )

def verify_admin_password(password: str) -> bool:
    """관리자 비밀번호 확인"""
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    return password == admin_password

def is_admin_authenticated(request: Request) -> bool:
    """관리자 인증 여부 확인"""
    return request.session.get("admin_authenticated", False)

async def require_admin_auth(request: Request):
    """관리자 인증 필요 시 로그인 페이지로 리다이렉트"""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login?redirect=" + str(request.url.path), status_code=303)
    return None

@app.get("/api/admin/inquiries")
async def get_inquiries(request: Request):
    """문의사항 목록 조회 API"""
    try:
        # 인증 확인
        if not is_admin_authenticated(request):
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "인증이 필요합니다."}
            )
        
        # 쿼리 파라미터
        status = request.query_params.get("status", None)
        limit = int(request.query_params.get("limit", 100))
        skip = int(request.query_params.get("skip", 0))
        
        # MongoDB에서 조회
        inquiries = await mongodb_client.get_inquiries(limit=limit, skip=skip, status=status)
        
        return JSONResponse(
            content={"success": True, "inquiries": inquiries}
        )
    except Exception as e:
        logger.error(f"문의사항 조회 API 오류: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "서버 오류가 발생했습니다."}
        )

@app.get("/api/admin/inquiries/stats")
async def get_inquiry_stats(request: Request):
    """문의사항 통계 API"""
    try:
        # 인증 확인
        if not is_admin_authenticated(request):
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "인증이 필요합니다."}
            )
        
        # 통계 조회
        total = await mongodb_client.get_inquiry_count()
        pending = await mongodb_client.get_inquiry_count(status="pending")
        replied = await mongodb_client.get_inquiry_count(status="replied")
        closed = await mongodb_client.get_inquiry_count(status="closed")
        
        return JSONResponse(
            content={
                "success": True,
                "total": total,
                "pending": pending,
                "replied": replied,
                "closed": closed
            }
        )
    except Exception as e:
        logger.error(f"문의사항 통계 API 오류: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "서버 오류가 발생했습니다."}
        )

@app.post("/api/admin/inquiries/{inquiry_id}/status")
async def update_inquiry_status(inquiry_id: str, request: Request):
    """문의사항 상태 업데이트 API"""
    try:
        # 인증 확인
        if not is_admin_authenticated(request):
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "인증이 필요합니다."}
            )
        
        data = await request.json()
        
        # 상태 업데이트
        status = data.get("status", "")
        if status not in ["pending", "replied", "closed"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "유효하지 않은 상태입니다."}
            )
        
        result = await mongodb_client.update_inquiry_status(inquiry_id, status)
        
        if result:
            logger.info(f"문의사항 상태 업데이트 성공: {inquiry_id} -> {status}")
            return JSONResponse(
                content={"success": True, "message": "상태가 업데이트되었습니다."}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "문의사항을 찾을 수 없습니다."}
            )
    except Exception as e:
        logger.error(f"문의사항 상태 업데이트 API 오류: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "서버 오류가 발생했습니다."}
        )

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

@app.post("/api/bithumb/test")
async def test_bithumb_api(request: Request):
    try:
        data = await request.json()
        api_version = data.get("apiVersion")
        # API Key 설정 (환경변수에서 불러오기 - 보안 방식)
        api_key = os.getenv("BITHUMB_API_KEY")
        secret_key = os.getenv("BITHUMB_SECRET_KEY")
        
        endpoint = data.get("selectedEndpoint")
        method = data.get("method", "POST")
        
        # API Key 검증
        if not api_key or not secret_key:
            return {
                "success": False,
                "requestUrl": "",
                "requestHeaders": {},
                "requestBody": "",
                "result": {"error": "API Key를 설정해주세요. \n환경변수 BITHUMB_API_KEY, BITHUMB_SECRET_KEY를 .env 파일에 설정하세요."}
            }
        base_url = "https://api.bithumb.com/"
        # v2 API의 경우 URL 구조가 다를 수 있음
        if api_version == "v2":
            endpoint_url = base_url + endpoint
        else:
            endpoint_url = base_url + endpoint

        params = data.get("params", {}) or {}
        # 빗썸 API v2는 정확한 대소문자를 요구하므로 변환하지 않음
        # lowercase_keys = ['currency', 'order_currency', 'payment_currency']
        # for key in lowercase_keys:
        #     if key in params and isinstance(params[key], str):
        #         params[key] = params[key].lower()

        if not endpoint:
            return {"success": False, "result": {"error": "엔드포인트가 선택되지 않았습니다."}}

        if api_version == "v1":
            nonce = str(int(time.time() * 1000))
            req_params = OrderedDict()
            req_params['endpoint'] = f'/{endpoint}'
            if params:
                req_params.update(params)
            
            # [핵심 수정] safe='/' 옵션을 제거하여 '/'가 '%2F'로 인코딩되도록 함
            request_body_string = urlencode(req_params)

            data_to_sign = f"/{endpoint}\0{request_body_string}\0{nonce}"
            signature = hmac.new(secret_key.encode('utf-8'), data_to_sign.encode('utf-8'), hashlib.sha512)
            api_sign = base64.b64encode(signature.digest()).decode('utf-8')
            
            headers = {
                "Api-Key": api_key,
                "Api-Nonce": nonce,
                "Api-Sign": api_sign,
                "Content-Type": "application/x-www-form-urlencoded",
                "api-client-type": "0"
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint_url, headers=headers, content=request_body_string)

            return await handle_response(response, endpoint_url, headers, request_body_string)

        elif api_version == "v2":
            # 빗썸 공식 예시 코드와 동일한 방식
            print("=== 빗썸 공식 방식으로 JWT 토큰 생성 ===")
            
            # Generate access token (공식 예시 코드와 정확히 동일)
            payload = {
                'access_key': api_key,
                'nonce': str(uuid.uuid4()),
                'timestamp': round(time.time() * 1000)
            }
            
            print(payload, "\n")
            # 출금 API용 requestBody 초기화
            withdraw_request_body = None
            
            # 엔드포인트별 특별 처리
            if endpoint == 'v1/accounts':
                # 계좌 조회는 파라미터 없음
                params = {}
                print("계좌 조회: 파라미터 강제 제거")
            elif endpoint == 'v1/withdraws/coin' and params:
                # 출금 API는 query_hash 필요 (공식 예시와 정확히 동일)
                print("출금 API: query_hash 생성 필요")
                # 한글+띄어쓰기 그대로 유지: Raw 형태로 query string 생성
                requestBody = dict(**params)  # 공식 예시 방식
                
                # 한글과 띄어쓰기를 인코딩하지 않고 그대로 사용
                query_parts = []
                for key, value in requestBody.items():
                    query_parts.append(f"{key}={value}")
                raw_query = "&".join(query_parts)
                query = raw_query.encode('utf-8')
                hash = hashlib.sha512()
                hash.update(query)
                query_hash = hash.hexdigest()
                payload['query_hash'] = query_hash
                payload['query_hash_alg'] = 'SHA512'
                print(f"RequestBody: {requestBody}")
                print(f"Raw Query String (한글 그대로): {raw_query}")
                print(f"Query Bytes: {query}")
                print(f"Query Hash: {query_hash}")
                
                # requestBody를 저장하여 나중에 사용
                withdraw_request_body = requestBody
            
            # JWT 토큰 생성 (공식 예시와 동일)
            try:
                # jwt_token = jwt.encode(payload, secretKey)
                jwt_token_raw = jwt.encode(payload, secret_key)
                
                # PyJWT 1.7.1은 bytes를 반환하므로 문자열로 변환
                if isinstance(jwt_token_raw, bytes):
                    jwt_token = jwt_token_raw.decode('utf-8')
                else:
                    jwt_token = jwt_token_raw
                    
                authorization_token = f"Bearer {jwt_token}"
                print(f"JWT Token: {jwt_token}")
                print(f"Authorization Token: {authorization_token}")
            except Exception as e:
                return {
                    "success": False,
                    "requestUrl": endpoint_url,
                    "requestHeaders": {},
                    "requestBody": "",
                    "result": {"error": f"JWT 토큰 생성 실패: {str(e)}. Secret Key를 확인해주세요."}
                }
            
            # 헤더 설정 (공식 예시에 맞게)
            headers = {
                'Authorization': authorization_token
            }
            
            # POST 요청시 Content-Type 추가 (출금 API 등)
            if method == 'POST':
                headers['Content-Type'] = 'application/json'
                
            print(f"Headers: {headers}")
            

            
            # 요청 전송 (공식 예시 코드 참고)
            print(f"=== API 호출 시작 ===")
            print(f"URL: {endpoint_url}")
            print(f"Headers: {headers}")
            print(f"Method: {method}")
            if params:
                print(f"Params: {params}")
            
            try:
                # Call API (공식 예시와 동일)
                async with httpx.AsyncClient() as client:
                    if method == "GET":
                        response = await client.get(endpoint_url, headers=headers)
                    elif method == "DELETE":
                        response = await client.delete(endpoint_url, headers=headers)
                    else: # POST
                        # 공식 예시: data=json.dumps(requestBody)
                        if endpoint == 'v1/withdraws/coin' and withdraw_request_body:
                            # 공식 예제와 동일: data=json.dumps(requestBody)
                            json_data = json.dumps(withdraw_request_body)
                            print(f"=== 출금 API 요청 데이터 ===")
                            print(f"RequestBody: {withdraw_request_body}")
                            print(f"JSON Data: {json_data}")
                            response = await client.post(endpoint_url, headers=headers, data=json_data)
                        else:
                            json_data = json.dumps(params or {})
                            response = await client.post(endpoint_url, headers=headers, data=json_data)
                
                # handle to success or fail (공식 예시와 동일)
                print(f"Status Code: {response.status_code}")
                try:
                    response_json = response.json()
                    print(f"Response: {response_json}")
                except:
                    print(f"Response Text: {response.text}")
                    
            except Exception as err:
                # handle exception (공식 예시와 동일)
                print(f"Exception: {err}")
                return {
                    "success": False,
                    "requestUrl": endpoint_url,
                    "requestHeaders": headers,
                    "requestBody": params,
                    "result": {"error": f"API 호출 실패: {str(err)}"}
                }
            
            display_body = json.dumps(params, ensure_ascii=False) if method in ['POST', 'PUT', 'DELETE'] and params else params
            
            # v2 API 에러 처리
            if response.status_code == 401:
                return {
                    "success": False,
                    "requestUrl": endpoint_url,
                    "requestHeaders": headers,
                    "requestBody": display_body,
                    "result": {
                        "error": "JWT 토큰 검증에 실패했습니다. API Key와 Secret Key를 확인해주세요.",
                        "status_code": response.status_code,
                        "response_text": response.text
                    }
                }
            
            return await handle_response(response, endpoint_url, headers, display_body)

        else:
            return {"success": False, "result": {"error": "지원하지 않는 API 버전입니다."}}

    except Exception as e:
        return {
            "success": False,
            "requestUrl": "",
            "requestHeaders": {},
            "result": {"error": str(e), "traceback": traceback.format_exc()}
        }

# [수정됨] 공통 응답 처리 함수
async def handle_response(response, url, headers, body):
    # body가 딕셔너리나 리스트일 경우 예쁘게 출력하기 위해 json.dumps 사용
    request_body_display = body
    if isinstance(body, (dict, list)):
        try:
            request_body_display = json.dumps(body, indent=2, ensure_ascii=False)
        except TypeError:
            request_body_display = str(body)

    try:
        result = response.json()
    except json.JSONDecodeError:
        return {
            "success": False, "requestUrl": url, "requestHeaders": headers, "requestBody": request_body_display,
            "result": {"error": "응답이 유효한 JSON 형식이 아닙니다.", "raw": response.text}
        }

    success = False
    if isinstance(result, dict):
        if result.get("status") == "0000":
            success = True
    elif isinstance(result, list):
        if response.status_code == 200:
            success = True

    return {
        "success": success, "requestUrl": url, "requestHeaders": headers, "requestBody": request_body_display, "result": result
    }

# 챗봇 관련 엔드포인트
@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """챗봇 페이지"""
    return templates.TemplateResponse("chatbot.html", {"request": request})

@app.post("/api/chat")
@traceable(name="chat_endpoint", run_type="chain")
async def chat(request: Request):
    """챗봇 메시지 처리"""
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        session_id = data.get("session_id", str(uuid.uuid4()))
        
        if not message:
            return JSONResponse(
                content={"error": "메시지를 입력해주세요."},
                status_code=400
            )
        
        # OpenAI API 키 확인
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            return JSONResponse(
                content={"error": "OpenAI API 키가 설정되지 않았습니다. OPENAI_API_KEY 환경변수를 설정해주세요."},
                status_code=500
            )
        
        # 로깅 재확인 (요청마다)
        chatbot_logger = logging.getLogger("chatbot.chatbot_graph")
        chatbot_logger.propagate = True
        chatbot_logger.handlers.clear()
        chatbot_logger.setLevel(log_level)
        
        # 챗봇 그래프 가져오기
        print(f"[MAIN] 채팅 요청 수신: 세션={session_id}, 메시지={message[:50]}...", file=sys.stdout, flush=True)
        logger.info(f"채팅 요청 수신: 세션={session_id}, 메시지={message[:50]}...")
        try:
            print("[MAIN] 챗봇 그래프 가져오는 중...", file=sys.stdout, flush=True)
            graph = get_chatbot_graph()
            print("[MAIN] 챗봇 그래프 초기화 완료", file=sys.stdout, flush=True)
            logger.info("챗봇 그래프 초기화 완료")
        except Exception as graph_error:
            logger.error(f"챗봇 초기화 실패: {graph_error}", exc_info=True)
            return JSONResponse(
                content={"error": f"챗봇 초기화 실패: {str(graph_error)}"},
                status_code=500
            )
        
        # MongoDB에서 이전 대화 기록 가져오기
        history_messages = []
        try:
            history = await mongodb_client.get_conversation_history(session_id, limit=10)
            for msg in history:
                if msg.get("role") == "user":
                    history_messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    history_messages.append(AIMessage(content=msg.get("content", "")))
        except Exception as e:
            logger.warning(f"대화 기록 조회 실패 (계속 진행): {e}")
        
        # 상태 초기화 (기본값 함수 사용 + 이전 대화 기록 + 현재 메시지)
        initial_state = get_default_chat_state(
            session_id=session_id,
            messages=history_messages + [HumanMessage(content=message)]
        )
        
        logger.info("그래프 실행 시작...")
        print("[MAIN] 그래프 실행 시작...", file=sys.stdout, flush=True)
        # 그래프 실행
        result = await graph.ainvoke(initial_state)
        print("[MAIN] 그래프 실행 완료", file=sys.stdout, flush=True)
        logger.info("그래프 실행 완료")
        
        # 디버그 로깅 (그래프 실행 결과 상태 확인)
        logger.info(f"그래프 실행 결과 키: {list(result.keys())}")
        logger.info(f"DB 검색 결과 개수: {len(result.get('db_search_results', []))}")
        logger.info(f"Deep Research 필요: {result.get('needs_deep_research', None)}")
        
        # 마지막 메시지 (AI 응답) 추출
        if result.get("messages"):
            ai_message = result["messages"][-1]
            response_text = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
        else:
            response_text = "응답을 생성할 수 없습니다."
        
        # 점수 정보 추출 (항상 수집, debug 파라미터로 표시 여부 결정)
        debug_param = data.get("debug", False)
        
        # 상태 정보 추출
        db_search_results = result.get("db_search_results", [])
        needs_deep_research = result.get("needs_deep_research", None)
        
        logger.info(f"상태 정보 추출 - DB 결과: {len(db_search_results)}개, Deep Research: {needs_deep_research}")
        
        # 벡터 검색 점수 정보
        similarity_scores = []
        if db_search_results:
            logger.info(f"벡터 검색 결과 발견: {len(db_search_results)}개")
            for i, result_item in enumerate(db_search_results):
                score = result_item.get("score", 0.0)
                similarity_scores.append({
                    "rank": i + 1,
                    "score": float(score),
                    "score_formatted": f"{score:.4f}",
                    "text_preview": result_item.get("text", "")[:100] + "...",
                    "source": result_item.get("source", ""),
                    "threshold": float(config.SIMILARITY_THRESHOLD),
                    "threshold_formatted": f"{config.SIMILARITY_THRESHOLD:.2f}",
                    "passed": float(score) > config.SIMILARITY_THRESHOLD
                })
            logger.info(f"점수 정보 생성: {len(similarity_scores)}개")
        else:
            logger.warning("벡터 검색 결과가 없습니다. db_search_results가 비어있음")
            logger.debug(f"전체 결과 상태 키: {list(result.keys())}")
        
        debug_info = {
            "similarity_scores": similarity_scores,
            "needs_deep_research": needs_deep_research,
            "threshold": float(config.SIMILARITY_THRESHOLD),
            "threshold_formatted": f"{config.SIMILARITY_THRESHOLD:.2f}",
            "web_search_results_count": len(result.get("web_search_results", [])),
            "summarized_results_count": len(result.get("summarized_results", [])),
            "compressed_results_count": len(result.get("compressed_results", [])),
            "state_keys": list(result.keys())  # 디버깅용
        }
        
        response_data = {
            "response": response_text,
            "session_id": session_id
        }
        
        # debug 파라미터가 있으면 디버그 정보 포함
        if debug_param:
            response_data["debug"] = debug_info
            logger.info(f"디버그 정보 포함: 점수 {len(similarity_scores)}개, Deep Research: {needs_deep_research}")
        else:
            logger.info(f"디버그 모드 아님 - 점수 정보 수집됨: {len(similarity_scores)}개 (표시 안 함)")
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            content={"error": f"처리 중 오류가 발생했습니다: {str(e)}"},
            status_code=500
        )


def extract_search_info_from_node_output(node_name: str, output: dict) -> dict:
    """
    노드 출력에서 검색 정보를 추출하여 표준화된 형식으로 반환
    
    Args:
        node_name: 노드 이름
        output: 노드의 출력 딕셔너리
        
    Returns:
        표준화된 검색 정보 딕셔너리 (없으면 빈 딕셔너리)
    """
    if not isinstance(output, dict):
        return {}
    
    # 검색 결과 정보 추출
    db_search_results = output.get("db_search_results", [])
    web_search_results = output.get("web_search_results", [])
    search_queries = output.get("search_queries", [])
    
    # FAQ specialist의 경우: db_search_results에 support_results가 포함될 수 있음
    # support_results는 source가 "bithumb_support"이므로 이를 구분
    if node_name == "faq_specialist" and db_search_results:
        # support_results와 실제 DB 결과 분리
        support_results_list = [r for r in db_search_results if r.get("source") == "bithumb_support"]
        actual_db_results = [r for r in db_search_results if r.get("source") != "bithumb_support"]
        
        # support_results를 web_results로 처리
        if support_results_list:
            web_search_results = support_results_list + web_search_results
        db_search_results = actual_db_results
    
    # 검색 정보가 있으면 표준화된 형식으로 변환
    search_info = {}
    if db_search_results:
        search_info["db_results"] = [
            {
                "title": r.get("title") or r.get("text", "")[:100] or "제목 없음",
                "url": r.get("url", ""),
                "score": r.get("score", 0),
                "snippet": r.get("snippet", r.get("text", ""))[:150]
            }
            for r in db_search_results[:3]
        ]
    if web_search_results:
        search_info["web_results"] = [
            {
                "title": r.get("title") or r.get("text", "")[:100] or "제목 없음",
                "url": r.get("href") or r.get("url", ""),
                "snippet": r.get("snippet") or r.get("body") or r.get("text", "")[:150]
            }
            for r in web_search_results[:3]
        ]
    if search_queries:
        search_info["queries"] = search_queries[:5]
    
    # FAQ specialist의 경우 검색 쿼리 정보 추가 (사용자 메시지 기반)
    if node_name == "faq_specialist" and not search_info.get("queries"):
        # 사용자 메시지를 검색 쿼리로 사용
        user_message = ""
        messages = output.get("messages", [])
        if messages:
            for msg in reversed(messages):
                if hasattr(msg, "content") and isinstance(msg.content, str):
                    # HumanMessage 찾기
                    if "HumanMessage" in str(type(msg)) or not hasattr(msg, "role"):
                        user_message = msg.content
                        break
        if user_message:
            search_info["queries"] = [user_message[:100]]
    
    return search_info


@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    """스트리밍 채팅 엔드포인트 (Server-Sent Events)
    
    LangGraph 1.0의 astream_events를 사용하여 실제 LLM 토큰 스트리밍을 구현합니다.
    - 노드별 진행 상황 실시간 전송
    - 실제 LLM 토큰 생성 즉시 전송 (실시간 스트리밍)
    - 완료 시 done 이벤트 전송
    """
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        session_id = data.get("session_id", str(uuid.uuid4()))
        
        if not message:
            async def error_stream():
                yield f"data: {json.dumps({'type': 'error', 'content': '메시지를 입력해주세요.'})}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")
        
        logger.info(f"[STREAM] 스트리밍 요청 - Session: {session_id}, Message: {message[:50]}...")
        
        # 그래프 가져오기
        graph = get_chatbot_graph()
        
        # MongoDB에서 이전 대화 기록 가져오기
        history_messages = []
        try:
            history = await mongodb_client.get_conversation_history(session_id, limit=10)
            for msg in history:
                if msg.get("role") == "user":
                    history_messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    history_messages.append(AIMessage(content=msg.get("content", "")))
        except Exception as e:
            logger.warning(f"[STREAM] 대화 기록 조회 실패 (계속 진행): {e}")
        
        # 상태 초기화
        initial_state = get_default_chat_state(
            session_id=session_id,
            messages=history_messages + [HumanMessage(content=message)]
        )
        
        async def generate_stream():
            """실제 LLM 토큰 스트리밍 이벤트 생성"""
            final_response = ""
            current_node = None
            accumulated_content = {}  # 노드별 누적 콘텐츠
            
            # 노드 표시 이름 매핑
            node_display_names = {
                "router": "🔀 라우팅 중...",
                "simple_chat_specialist": "💬 응답 생성 중...",
                "faq_specialist": "📚 FAQ 검색 중...",
                "transaction_specialist": "🔍 트랜잭션 조회 중...",
                "planner": "📋 검색 계획 중...",
                "researcher": "🔎 웹 검색 중...",
                "grader": "📊 결과 평가 중...",
                "writer": "✍️ 응답 작성 중...",
                "intent_clarifier": "🤔 의도 확인 중...",
                "save_response": "💾 저장 중..."
            }
            
            # 응답 생성 노드 목록 (LLM 토큰 스트리밍 대상)
            response_nodes = {"writer", "simple_chat_specialist", "faq_specialist", "intent_clarifier", "transaction_specialist"}
            
            try:
                # 시작 이벤트
                yield f"data: {json.dumps({'type': 'start', 'session_id': session_id})}\n\n"
                
                # LangGraph 1.0의 astream_events 사용 (실제 LLM 토큰 스트리밍)
                # include_types를 제거하여 모든 이벤트 추적 (노드 진행 상황 + LLM 토큰)
                async for event in graph.astream_events(
                    initial_state,
                    version="v2"  # LangGraph 1.0+ 필수
                ):
                    event_type = event.get("event", "")
                    event_name = event.get("name", "")
                    
                    # 노드 시작 이벤트 (모든 노드 추적)
                    if event_type == "on_chain_start":
                        # 노드 이름 추출 (체인 이름에서)
                        node_name = event_name.split("/")[-1] if "/" in event_name else event_name
                        if node_name in node_display_names:
                            current_node = node_name
                            display_name = node_display_names[node_name]
                            yield f"data: {json.dumps({'type': 'node', 'node': node_name, 'display': display_name})}\n\n"
                            # 노드별 콘텐츠 초기화
                            if node_name in response_nodes:
                                accumulated_content[node_name] = ""
                    
                    # 실제 LLM 토큰 스트리밍 (핵심!)
                    elif event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk:
                            # 토큰 콘텐츠 추출
                            if hasattr(chunk, "content") and chunk.content:
                                token_content = chunk.content
                                # 현재 노드에 토큰 추가
                                if current_node and current_node in accumulated_content:
                                    accumulated_content[current_node] += token_content
                                    
                                    # 누적된 콘텐츠에서 JSON 패턴 확인
                                    accumulated = accumulated_content[current_node]
                                    
                                    # JSON이 시작되었는지 확인 ({로 시작하고 키워드 포함)
                                    json_keywords = [
                                        '"search_queries"', '"research_plan"', '"priority"',
                                        '"score"', '"is_sufficient"', '"feedback"', '"missing_information"'
                                    ]
                                    if accumulated.strip().startswith('{') and any(
                                        keyword in accumulated[:500] 
                                        for keyword in json_keywords
                                    ):
                                        # JSON 블록이 완료되었는지 확인 (매칭되는 } 찾기)
                                        brace_count = accumulated.count('{') - accumulated.count('}')
                                        if brace_count == 0 and '}' in accumulated:
                                            # JSON 블록 완료 - 이후 콘텐츠만 전송
                                            json_end = accumulated.rfind('}')
                                            if json_end != -1:
                                                after_json = accumulated[json_end + 1:].lstrip()
                                                # JSON 뒤의 콘텐츠가 있으면 전송
                                                if after_json:
                                                    # JSON 이후의 새 토큰만 전송
                                                    prev_accumulated = accumulated[:-len(token_content)] if len(accumulated) >= len(token_content) else ""
                                                    prev_after_json = prev_accumulated[prev_accumulated.rfind('}') + 1:].lstrip() if '}' in prev_accumulated else ""
                                                    new_content = after_json[len(prev_after_json):] if prev_after_json else after_json
                                                    if new_content:
                                                        yield f"data: {json.dumps({'type': 'token', 'content': new_content})}\n\n"
                                                continue
                                            else:
                                                # JSON이 아직 완료되지 않음 - 전송하지 않음
                                                continue
                                        else:
                                            # JSON 블록이 아직 완료되지 않음 - 전송하지 않음
                                            continue
                                
                                # JSON이 아닌 경우에만 전송
                                yield f"data: {json.dumps({'type': 'token', 'content': token_content})}\n\n"
                    
                    # 노드 완료 이벤트
                    elif event_type == "on_chain_end":
                        # 노드 이름 추출
                        node_name = event_name.split("/")[-1] if "/" in event_name else event_name
                        
                        # 노드 완료 시 검색 정보 추출 및 전송 (공통 함수 사용)
                        output = event.get("data", {}).get("output", {})
                        search_info = extract_search_info_from_node_output(node_name, output)
                        
                        # 검색 정보가 있으면 전송
                        if search_info:
                            yield f"data: {json.dumps({'type': 'node_search', 'node': node_name, 'search_info': search_info})}\n\n"
                        
                        if node_name in response_nodes:
                            # 최종 응답 추출
                            if isinstance(output, dict):
                                messages = output.get("messages", [])
                                if messages:
                                    last_msg = messages[-1]
                                    content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                                    if content:
                                        # JSON 구조 제거
                                        cleaned_content = content.strip()
                                        
                                        # {로 시작하고 JSON 키워드를 포함하는 경우 제거
                                        json_keywords = [
                                            '"search_queries"', '"research_plan"', '"priority"',
                                            '"score"', '"is_sufficient"', '"feedback"', '"missing_information"'
                                        ]
                                        if cleaned_content.startswith('{') and any(
                                            keyword in cleaned_content[:500] 
                                            for keyword in json_keywords
                                        ):
                                            # 매칭되는 } 찾기
                                            brace_count = 0
                                            end_idx = 0
                                            for i in range(len(cleaned_content)):
                                                if cleaned_content[i] == '{':
                                                    brace_count += 1
                                                elif cleaned_content[i] == '}':
                                                    brace_count -= 1
                                                    if brace_count == 0:
                                                        end_idx = i + 1
                                                        break
                                            
                                            if end_idx > 0:
                                                cleaned_content = cleaned_content[end_idx:].lstrip()
                                                cleaned_content = re.sub(r'^\s*\n\s*\n\s*', '', cleaned_content).strip()
                                        
                                        final_response = cleaned_content
                                        
                                        # transaction_specialist는 LLM을 사용하지 않으므로 즉시 토큰으로 전송
                                        if node_name == "transaction_specialist":
                                            # 토큰으로 스트리밍 (전체 내용을 한 번에 전송)
                                            yield f"data: {json.dumps({'type': 'token', 'content': cleaned_content})}\n\n"
                                            accumulated_content[node_name] = cleaned_content
                                        else:
                                            # 누적된 콘텐츠가 없으면 최종 응답 사용
                                            if node_name in accumulated_content and not accumulated_content[node_name]:
                                                accumulated_content[node_name] = cleaned_content
                    
                    # 그래프 완료 이벤트
                    elif event_type == "on_chain_end" and event_name == "__end__":
                        # 최종 응답이 없으면 마지막 노드의 누적 콘텐츠 사용
                        if not final_response and accumulated_content:
                            final_response = list(accumulated_content.values())[-1] if accumulated_content else ""
                            # JSON 구조 제거
                            if final_response:
                                cleaned = final_response.strip()
                                json_keywords = [
                                    '"search_queries"', '"research_plan"', '"priority"',
                                    '"score"', '"is_sufficient"', '"feedback"', '"missing_information"'
                                ]
                                if cleaned.startswith('{') and any(
                                    keyword in cleaned[:500] 
                                    for keyword in json_keywords
                                ):
                                    brace_count = 0
                                    end_idx = 0
                                    for i in range(len(cleaned)):
                                        if cleaned[i] == '{':
                                            brace_count += 1
                                        elif cleaned[i] == '}':
                                            brace_count -= 1
                                            if brace_count == 0:
                                                end_idx = i + 1
                                                break
                                    if end_idx > 0:
                                        cleaned = cleaned[end_idx:].lstrip()
                                        cleaned = re.sub(r'^\s*\n\s*\n\s*', '', cleaned).strip()
                                        final_response = cleaned
                
                # 완료 이벤트 전에 최종 응답에서 JSON 제거 (이중 안전장치)
                if final_response:
                    cleaned_final = final_response.strip()
                    json_keywords = [
                        '"search_queries"', '"research_plan"', '"priority"',
                        '"score"', '"is_sufficient"', '"feedback"', '"missing_information"'
                    ]
                    if cleaned_final.startswith('{') and any(
                        keyword in cleaned_final[:500] 
                        for keyword in json_keywords
                    ):
                        brace_count = 0
                        end_idx = 0
                        for i in range(len(cleaned_final)):
                            if cleaned_final[i] == '{':
                                brace_count += 1
                            elif cleaned_final[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i + 1
                                    break
                        if end_idx > 0:
                            cleaned_final = cleaned_final[end_idx:].lstrip()
                            cleaned_final = re.sub(r'^\s*\n\s*\n\s*', '', cleaned_final).strip()
                            final_response = cleaned_final
                
                # 완료 이벤트
                yield f"data: {json.dumps({'type': 'done', 'final_response': final_response})}\n\n"
                
                # MongoDB에 대화 저장
                try:
                    await mongodb_client.save_message(session_id, "user", message)
                    if final_response:
                        await mongodb_client.save_message(session_id, "assistant", final_response)
                except Exception as e:
                    logger.error(f"[STREAM] 메시지 저장 실패: {e}")
                
            except Exception as e:
                logger.error(f"[STREAM] 스트리밍 중 오류: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'content': f'스트리밍 중 오류가 발생했습니다: {str(e)}'})}\n\n"
        
        # StreamingResponse 반환
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # nginx 버퍼링 비활성화
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )
        
    except Exception as e:
        logger.error(f"[STREAM] 스트리밍 요청 처리 실패: {e}", exc_info=True)
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'content': f'처리 중 오류가 발생했습니다: {str(e)}'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")


@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """대화 기록 조회"""
    try:
        history = await mongodb_client.get_conversation_history(session_id, limit=50)
        # datetime 객체를 문자열로 변환 (JSON 직렬화를 위해)
        serialized_history = []
        for msg in history:
            serialized_msg = dict(msg)
            if "created_at" in serialized_msg and hasattr(serialized_msg["created_at"], "isoformat"):
                serialized_msg["created_at"] = serialized_msg["created_at"].isoformat()
            # _id도 문자열로 변환
            if "_id" in serialized_msg:
                serialized_msg["_id"] = str(serialized_msg["_id"])
            serialized_history.append(serialized_msg)
        return JSONResponse(content={"history": serialized_history})
    except Exception as e:
        logger.error(f"대화 기록 조회 실패: {e}", exc_info=True)
        return JSONResponse(
            content={"error": f"대화 기록 조회 실패: {str(e)}"},
            status_code=500
        )

@app.delete("/api/chat/history/{session_id}")
async def clear_chat_history(session_id: str):
    """대화 기록 삭제"""
    try:
        success = await mongodb_client.clear_conversation(session_id)
        return JSONResponse(content={"success": success})
    except Exception as e:
        return JSONResponse(
            content={"error": f"대화 기록 삭제 실패: {str(e)}"},
            status_code=500
        )

@app.post("/api/crawl")
async def crawl_website(request: Request):
    """웹사이트 크롤링 및 벡터 DB 저장"""
    try:
        data = await request.json()
        url = data.get("url", "")
        
        if not url:
            return JSONResponse(
                content={"error": "URL을 입력해주세요."},
                status_code=400
            )
        
        # 비동기로 크롤링 실행 (백그라운드 작업)
        asyncio.create_task(vector_store.crawl_and_store(url))
        
        return JSONResponse(content={
            "message": "크롤링이 시작되었습니다. 완료까지 몇 분 걸릴 수 있습니다.",
            "url": url
        })
        
    except Exception as e:
        return JSONResponse(
            content={"error": f"크롤링 시작 실패: {str(e)}"},
            status_code=500
        )

if __name__ == "__main__":
    ssl_keyfile = os.getenv("SSL_KEY_PATH")
    ssl_certfile = os.getenv("SSL_CERT_PATH")
    
    # uvicorn 로그 설정
    log_level_uvicorn = os.getenv("LOG_LEVEL", "info").lower()
    
    # uvicorn 시작 전에 로깅 재확인 및 강제 적용
    logger.info("서버 시작 준비 중...")
    
    # uvicorn이 로깅을 재설정하지 않도록 로깅 설정 재확인
    def setup_logging():
        """로깅 설정 재적용 (uvicorn 시작 후에도 유지)"""
        root = logging.getLogger()
        root.setLevel(log_level)
        # 핸들러가 없으면 추가
        if not root.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(log_level)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            root.addHandler(handler)
        # 하위 로거들도 재설정
        for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "chatbot"]:
            lg = logging.getLogger(logger_name)
            lg.setLevel(log_level)
            lg.propagate = True
            lg.handlers.clear()
    
    # uvicorn Config를 사용하여 로깅 제어
    import uvicorn.config
    
    # uvicorn 기본 로깅 비활성화 및 우리 로깅 사용
    # propagate: True로 설정하여 루트 로거의 핸들러도 사용하도록 함
    uvicorn_log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "access": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            # propagate: True로 설정하여 루트 로거의 핸들러도 사용
            "uvicorn": {"handlers": ["default"], "level": log_level_str, "propagate": True},
            "uvicorn.error": {"handlers": ["default"], "level": log_level_str, "propagate": True},
            "uvicorn.access": {"handlers": ["access"], "level": log_level_str, "propagate": True},
        },
        "root": {
            "level": log_level_str,
            "handlers": ["default"],
        },
    }
    
    if ssl_keyfile and ssl_certfile:
        logger.info("SSL 모드로 서버 시작 (포트 443)")
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=443,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            log_level=log_level_uvicorn,
            log_config=uvicorn_log_config,  # 우리 로깅 설정 사용
            use_colors=False,
            access_log=True
        )
    else:
        logger.info("일반 모드로 서버 시작 (포트 8000)")
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            log_level=log_level_uvicorn,
            log_config=uvicorn_log_config,  # 우리 로깅 설정 사용
            use_colors=False,
            access_log=True
        )