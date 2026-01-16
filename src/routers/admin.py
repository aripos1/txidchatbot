"""
Admin 라우터
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from chatbot import mongodb_client
from src.services.admin_service import verify_admin_password, is_admin_authenticated, require_admin_auth
import logging
import bcrypt
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["admin"])

def register_admin_routes(app, templates: Jinja2Templates):
    """Admin 라우트를 FastAPI 앱에 등록"""
    
    # Helper functions는 src.services.admin_service에서 import
    # 기존 정의 제거됨
    
    # Pages
    @app.get("/admin/login", response_class=HTMLResponse)
    async def admin_login_page(request: Request):
        """관리자 로그인 페이지"""
        if is_admin_authenticated(request):
            return RedirectResponse(url="/admin/inquiries", status_code=303)
        redirect_url = request.query_params.get("redirect", "/admin/inquiries")
        return templates.TemplateResponse("admin/admin_login.html", {"request": request, "redirect_url": redirect_url})
    
    @app.get("/admin/inquiries", response_class=HTMLResponse)
    async def admin_inquiries_page(request: Request):
        """문의사항 관리 페이지"""
        redirect = await require_admin_auth(request)
        if redirect:
            return redirect
        return templates.TemplateResponse("admin/admin_inquiries.html", {"request": request})
    
    @app.get("/admin/inquiries/stats", response_class=HTMLResponse)
    async def admin_inquiries_stats_page(request: Request):
        """문의사항 통계 페이지"""
        redirect = await require_admin_auth(request)
        if redirect:
            return redirect
        return templates.TemplateResponse("admin/admin_stats.html", {"request": request})
    
    @app.get("/admin/chat/stats", response_class=HTMLResponse)
    async def admin_chat_stats_page(request: Request):
        """채팅 통계 페이지"""
        redirect = await require_admin_auth(request)
        if redirect:
            return redirect
        return templates.TemplateResponse("admin/admin_chat_stats.html", {"request": request})
    
    # API - Authentication
    @app.post("/admin/login")
    async def admin_login(request: Request):
        """관리자 로그인 API"""
        try:
            data = await request.json()
            password = data.get("password", "")
            if await verify_admin_password(password):
                request.session["admin_authenticated"] = True
                redirect_url = data.get("redirect_url", "/admin/inquiries")
                logger.info(f"관리자 로그인 성공: {request.client.host if request.client else 'unknown'}")
                response = JSONResponse(content={"success": True, "redirect_url": redirect_url})
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
        return JSONResponse(content={"success": True, "message": "로그아웃되었습니다."})
    
    # API - Inquiries
    @app.get("/api/admin/inquiries")
    async def get_inquiries(request: Request):
        """문의사항 목록 조회 API"""
        try:
            if not is_admin_authenticated(request):
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "message": "인증이 필요합니다."}
                )
            status = request.query_params.get("status", None)
            limit = int(request.query_params.get("limit", 100))
            skip = int(request.query_params.get("skip", 0))
            inquiries = await mongodb_client.get_inquiries(limit=limit, skip=skip, status=status)
            return JSONResponse(content={"success": True, "inquiries": inquiries})
        except Exception as e:
            logger.error(f"문의사항 조회 API 오류: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "서버 오류가 발생했습니다."}
            )
    
    @app.get("/api/admin/inquiries/stats")
    async def get_inquiry_stats(request: Request):
        """문의사항 통계 API (기본 통계)"""
        try:
            if not is_admin_authenticated(request):
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "message": "인증이 필요합니다."}
                )
            # 기존 코드와 동일하게 구현
            total = await mongodb_client.get_inquiry_count()
            pending = await mongodb_client.get_inquiry_count(status="pending")
            replied = await mongodb_client.get_inquiry_count(status="replied")
            closed = await mongodb_client.get_inquiry_count(status="closed")
            return JSONResponse(content={
                "success": True,
                "total": total,
                "pending": pending,
                "replied": replied,
                "closed": closed
            })
        except Exception as e:
            logger.error(f"문의사항 통계 API 오류: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "서버 오류가 발생했습니다."}
            )
    
    @app.get("/api/admin/inquiries/detailed-stats")
    async def get_detailed_inquiry_stats(request: Request):
        """문의사항 상세 통계 API"""
        try:
            if not is_admin_authenticated(request):
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "message": "인증이 필요합니다."}
                )
            stats = await mongodb_client.get_detailed_inquiry_statistics()
            return JSONResponse(content={"success": True, "stats": stats})
        except Exception as e:
            logger.error(f"문의사항 상세 통계 API 오류: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "서버 오류가 발생했습니다."}
            )
    
    @app.post("/api/admin/inquiries/{inquiry_id}/status")
    async def update_inquiry_status(inquiry_id: str, request: Request):
        """문의사항 상태 변경 API"""
        try:
            if not is_admin_authenticated(request):
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "message": "인증이 필요합니다."}
                )
            data = await request.json()
            status = data.get("status", "")
            if status not in ["pending", "replied", "closed"]:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "유효하지 않은 상태입니다."}
                )
            result = await mongodb_client.update_inquiry_status(inquiry_id, status)
            if result:
                logger.info(f"문의사항 상태 업데이트 성공: {inquiry_id} -> {status}")
                return JSONResponse(content={"success": True, "message": "상태가 업데이트되었습니다."})
            else:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "message": "문의사항을 찾을 수 없습니다."}
                )
        except Exception as e:
            logger.error(f"문의사항 상태 변경 API 오류: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "서버 오류가 발생했습니다."}
            )
    
    # API - Chat Stats
    @app.get("/api/admin/chat/stats")
    async def get_chat_stats(request: Request):
        """채팅 상세 통계 API"""
        try:
            if not is_admin_authenticated(request):
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "message": "인증이 필요합니다."}
                )
            stats = await mongodb_client.get_chat_statistics()
            return JSONResponse(content={"success": True, "stats": stats})
        except Exception as e:
            logger.error(f"채팅 상세 통계 API 오류: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "서버 오류가 발생했습니다."}
            )
    
    @app.get("/api/admin/chat/content-stats")
    async def get_chat_content_stats(request: Request):
        """채팅 내용 분석 통계 API (AI 분석 포함)"""
        try:
            if not is_admin_authenticated(request):
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "message": "인증이 필요합니다."}
                )
            use_ai = request.query_params.get("use_ai", "true").lower() == "true"
            stats = await mongodb_client.get_chat_content_statistics(use_ai_analysis=use_ai)
            return JSONResponse(content={
                "success": True,
                "stats": stats,
                "ai_analysis_enabled": use_ai
            })
        except Exception as e:
            logger.error(f"채팅 내용 통계 API 오류: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "서버 오류가 발생했습니다."}
            )
    
    # API - Password
    @app.post("/api/admin/change-password")
    async def change_admin_password(request: Request):
        """관리자 비밀번호 변경 API"""
        try:
            if not is_admin_authenticated(request):
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "message": "인증이 필요합니다."}
                )
            data = await request.json()
            current_password = data.get("current_password", "")
            new_password = data.get("new_password", "")
            confirm_password = data.get("confirm_password", "")
            
            # 입력 검증
            if not current_password or not new_password or not confirm_password:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "모든 필드를 입력해주세요."}
                )
            if new_password != confirm_password:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "새 비밀번호가 일치하지 않습니다."}
                )
            if len(new_password) < 6:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "비밀번호는 최소 6자 이상이어야 합니다."}
                )
            
            # 현재 비밀번호 확인
            if not await verify_admin_password(current_password):
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "message": "현재 비밀번호가 일치하지 않습니다."}
                )
            
            # 새 비밀번호 해시화 및 저장
            new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            success = await mongodb_client.set_admin_password_hash(new_password_hash)
            
            if success:
                logger.info(f"관리자 비밀번호가 변경되었습니다: {request.client.host if request.client else 'unknown'}")
                return JSONResponse(content={"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."})
            else:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": "비밀번호 변경에 실패했습니다."}
                )
        except Exception as e:
            logger.error(f"비밀번호 변경 API 오류: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "서버 오류가 발생했습니다."}
            )
