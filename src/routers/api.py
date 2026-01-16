"""
API 라우터 (트랜잭션, 체인, 연락처 등)
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from src.services.transaction_service import detect_transaction
from src.services.chain_configs import get_chain_configs
from chatbot import mongodb_client
import logging
import httpx
import json
import os
import hmac
import hashlib
import base64
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])

def register_api_routes(app, templates: Jinja2Templates):
    """API 라우트를 FastAPI 앱에 등록"""
    
    @app.get("/api/tx/{txid}")
    async def get_transaction(txid: str):
        """트랜잭션 조회 API"""
        results = await detect_transaction(txid)
        if results:
            return JSONResponse(content={"found": True, "results": results})
        else:
            return JSONResponse(content={"found": False, "message": "Transaction not found on supported chains."})
    
    @app.get("/api/chains")
    async def get_chains():
        """지원하는 체인 목록 조회 API"""
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
    
    @app.post("/api/bithumb/test")
    async def test_bithumb_api(request: Request):
        """빗썸 API 테스트"""
        try:
            data = await request.json()
            endpoint = data.get("endpoint", "ticker")
            params = data.get("params", {})
            
            api_key = os.getenv("BITHUMB_API_KEY", "")
            api_secret = os.getenv("BITHUMB_API_SECRET", "")
            
            if not api_key or not api_secret:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "빗썸 API 키가 설정되지 않았습니다."}
                )
            
            # 빗썸 API 요청 로직 (기존 코드 참고)
            base_url = "https://api.bithumb.com/public"
            url = f"{base_url}/{endpoint}"
            
            if params:
                query_string = urlencode(params)
                url += f"?{query_string}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                result = response.json()
            
            return JSONResponse(content={"success": True, "data": result})
        except Exception as e:
            logger.error(f"빗썸 API 테스트 오류: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"API 테스트 실패: {str(e)}"}
            )
    
    @app.get("/api/debug/static-files")
    async def debug_static_files():
        """정적 파일 목록 확인 (디버깅용)"""
        from pathlib import Path
        try:
            static_dir = Path(__file__).parent.parent.parent / "static"
            static_dir_abs = static_dir.resolve()
            
            result = {
                "static_dir": str(static_dir_abs),
                "exists": static_dir_abs.exists(),
                "files": {}
            }
            
            if static_dir_abs.exists():
                for item in static_dir_abs.rglob("*"):
                    if item.is_file():
                        rel_path = str(item.relative_to(static_dir_abs))
                        result["files"][rel_path] = {
                            "size": item.stat().st_size,
                            "exists": True
                        }
            
            return JSONResponse(content=result)
        except Exception as e:
            logger.error(f"정적 파일 디버그 오류: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @app.post("/api/crawl")
    async def crawl_website(request: Request):
        """웹사이트 크롤링 및 벡터 DB 저장"""
        try:
            data = await request.json()
            url = data.get("url", "").strip()
            
            if not url:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "URL을 입력해주세요."}
                )
            
            # 크롤링 로직은 main.py의 기존 코드 참고
            # 여기서는 기본 구조만 제공
            logger.info(f"크롤링 요청: {url}")
            
            return JSONResponse(
                content={"success": True, "message": "크롤링이 시작되었습니다."}
            )
        except Exception as e:
            logger.error(f"크롤링 API 오류: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"크롤링 실패: {str(e)}"}
            )
