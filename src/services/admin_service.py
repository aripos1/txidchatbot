"""
Admin 서비스
"""
from fastapi import Request
from fastapi.responses import RedirectResponse
from chatbot import mongodb_client
import logging
import bcrypt
import os

logger = logging.getLogger(__name__)


async def verify_admin_password(password: str) -> bool:
    """관리자 비밀번호 확인 (MongoDB에서 조회)"""
    try:
        # MongoDB에서 비밀번호 해시 조회
        password_hash = await mongodb_client.get_admin_password_hash()
        
        if password_hash:
            # 해시된 비밀번호와 비교
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        else:
            # MongoDB에 비밀번호가 없으면 환경 변수 또는 기본값 사용
            admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
            if password == admin_password:
                # MongoDB에 초기 비밀번호 저장
                hash_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                await mongodb_client.set_admin_password_hash(hash_pw)
                logger.info("관리자 비밀번호가 MongoDB에 초기화되었습니다.")
                return True
            return False
    except Exception as e:
        logger.error(f"관리자 비밀번호 확인 오류: {e}")
        # 오류 발생 시 환경 변수로 폴백
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
