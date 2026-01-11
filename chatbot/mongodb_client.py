"""
MongoDB Atlas 연결 및 데이터베이스 클라이언트 모듈
"""
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from typing import Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
# 루트 로거로 전파되도록 설정
logger.propagate = True
logger.handlers.clear()

class MongoDBClient:
    """MongoDB Atlas 비동기 클라이언트"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.chat_collection = None
        self.inquiry_collection = None
        
    async def connect(self):
        """MongoDB Atlas에 연결"""
        try:
            # MongoDB Atlas 연결 문자열 (환경변수에서 가져오기)
            connection_string = os.getenv(
                "MONGODB_URI",
                "mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority"
            )
            
            database_name = os.getenv("MONGODB_DATABASE", "chatbot_db")
            
            if not connection_string or "username:password" in connection_string:
                logger.warning("MongoDB URI가 설정되지 않았습니다. MONGODB_URI 환경변수를 설정해주세요.")
                return False
            
            self.client = AsyncIOMotorClient(
                connection_string,
                serverSelectionTimeoutMS=5000,  # 5초 타임아웃
                connectTimeoutMS=5000,  # 연결 타임아웃 5초
                socketTimeoutMS=5000,  # 소켓 타임아웃 5초
                maxPoolSize=10,  # 최대 연결 풀 크기
                minPoolSize=1  # 최소 연결 풀 크기
            )
            
            # 연결 테스트 (타임아웃 설정)
            await asyncio.wait_for(
                self.client.admin.command('ping'),
                timeout=5.0  # 5초 타임아웃
            )
            
            self.db = self.client[database_name]
            self.chat_collection = self.db["conversations"]
            self.inquiry_collection = self.db["inquiries"]
            
            # 인덱스 생성 (성능 최적화)
            await self.chat_collection.create_index("session_id")
            await self.chat_collection.create_index("created_at")
            await self.inquiry_collection.create_index("email")
            await self.inquiry_collection.create_index("created_at")
            await self.inquiry_collection.create_index("status")
            
            logger.info(f"MongoDB Atlas 연결 성공: {database_name}")
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"MongoDB 연결 타임아웃 (5초)")
            if self.client:
                self.client.close()
                self.client = None
            return False
        except asyncio.CancelledError:
            logger.warning(f"MongoDB 연결이 취소되었습니다")
            if self.client:
                self.client.close()
                self.client = None
            return False
        except ConnectionFailure as e:
            logger.error(f"MongoDB 연결 실패: {e}")
            if self.client:
                self.client.close()
                self.client = None
            return False
        except Exception as e:
            logger.error(f"MongoDB 연결 오류: {e}")
            if self.client:
                self.client.close()
                self.client = None
            return False
    
    async def disconnect(self):
        """MongoDB 연결 종료"""
        if self.client:
            self.client.close()
            logger.info("MongoDB 연결 종료")
    
    async def save_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        """대화 메시지를 저장"""
        if self.chat_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return None
        
        message = {
            "session_id": session_id,
            "role": role,  # "user" or "assistant"
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.utcnow()
        }
        
        try:
            result = await self.chat_collection.insert_one(message)
            return result.inserted_id
        except Exception as e:
            logger.error(f"메시지 저장 실패: {e}")
            return None
    
    async def get_conversation_history(self, session_id: str, limit: int = 20):
        """대화 기록 조회"""
        if self.chat_collection is None:
            return []
        
        try:
            cursor = self.chat_collection.find(
                {"session_id": session_id}
            ).sort("created_at", -1).limit(limit)
            
            messages = await cursor.to_list(length=limit)
            # 시간 역순으로 정렬되어 있으므로 뒤집어서 시간순으로 반환
            messages.reverse()
            return messages
        except Exception as e:
            logger.error(f"대화 기록 조회 실패: {e}")
            return []
    
    async def clear_conversation(self, session_id: str):
        """대화 기록 삭제"""
        if self.chat_collection is None:
            return False
        
        try:
            result = await self.chat_collection.delete_many({"session_id": session_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"대화 기록 삭제 실패: {e}")
            return False
    
    async def save_inquiry(self, email: str, category: str, subject: str, message: str, metadata: dict = None):
        """문의사항 저장"""
        if self.inquiry_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return None
        
        inquiry = {
            "email": email,
            "category": category,
            "subject": subject,
            "message": message,
            "status": "pending",  # pending, replied, closed
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        try:
            result = await self.inquiry_collection.insert_one(inquiry)
            return result.inserted_id
        except Exception as e:
            logger.error(f"문의사항 저장 실패: {e}")
            return None
    
    async def get_inquiries(self, limit: int = 100, skip: int = 0, status: str = None):
        """문의사항 목록 조회"""
        if self.inquiry_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return []
        
        try:
            query = {}
            if status:
                query["status"] = status
            
            cursor = self.inquiry_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
            inquiries = await cursor.to_list(length=limit)
            
            # ObjectId와 datetime을 JSON 직렬화 가능한 형식으로 변환
            for inquiry in inquiries:
                inquiry["_id"] = str(inquiry["_id"])
                # datetime 객체를 ISO 형식 문자열로 변환 (UTC 표시)
                if "created_at" in inquiry and inquiry["created_at"]:
                    if isinstance(inquiry["created_at"], datetime):
                        inquiry["created_at"] = inquiry["created_at"].isoformat() + "Z"
                if "updated_at" in inquiry and inquiry["updated_at"]:
                    if isinstance(inquiry["updated_at"], datetime):
                        inquiry["updated_at"] = inquiry["updated_at"].isoformat() + "Z"
            
            return inquiries
        except Exception as e:
            logger.error(f"문의사항 조회 실패: {e}")
            return []
    
    async def get_inquiry_by_id(self, inquiry_id: str):
        """문의사항 ID로 조회"""
        if self.inquiry_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return None
        
        try:
            from bson import ObjectId
            inquiry = await self.inquiry_collection.find_one({"_id": ObjectId(inquiry_id)})
            if inquiry:
                inquiry["_id"] = str(inquiry["_id"])
                # datetime 객체를 ISO 형식 문자열로 변환 (UTC 표시)
                if "created_at" in inquiry and inquiry["created_at"]:
                    if isinstance(inquiry["created_at"], datetime):
                        inquiry["created_at"] = inquiry["created_at"].isoformat() + "Z"
                if "updated_at" in inquiry and inquiry["updated_at"]:
                    if isinstance(inquiry["updated_at"], datetime):
                        inquiry["updated_at"] = inquiry["updated_at"].isoformat() + "Z"
            return inquiry
        except Exception as e:
            logger.error(f"문의사항 조회 실패: {e}")
            return None
    
    async def update_inquiry_status(self, inquiry_id: str, status: str):
        """문의사항 상태 업데이트"""
        if self.inquiry_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return False
        
        try:
            from bson import ObjectId
            result = await self.inquiry_collection.update_one(
                {"_id": ObjectId(inquiry_id)},
                {"$set": {"status": status, "updated_at": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"문의사항 상태 업데이트 실패: {e}")
            return False
    
    async def get_inquiry_count(self, status: str = None):
        """문의사항 개수 조회"""
        if self.inquiry_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return 0
        
        try:
            query = {}
            if status:
                query["status"] = status
            count = await self.inquiry_collection.count_documents(query)
            return count
        except Exception as e:
            logger.error(f"문의사항 개수 조회 실패: {e}")
            return 0

# 전역 MongoDB 클라이언트 인스턴스
mongodb_client = MongoDBClient()

