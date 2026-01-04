"""
MongoDB Atlas 연결 및 데이터베이스 클라이언트 모듈
"""
import os
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
                serverSelectionTimeoutMS=5000
            )
            
            # 연결 테스트
            await self.client.admin.command('ping')
            
            self.db = self.client[database_name]
            self.chat_collection = self.db["conversations"]
            
            # 인덱스 생성 (성능 최적화)
            await self.chat_collection.create_index("session_id")
            await self.chat_collection.create_index("created_at")
            
            logger.info(f"MongoDB Atlas 연결 성공: {database_name}")
            return True
            
        except ConnectionFailure as e:
            logger.error(f"MongoDB 연결 실패: {e}")
            return False
        except Exception as e:
            logger.error(f"MongoDB 연결 오류: {e}")
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

# 전역 MongoDB 클라이언트 인스턴스
mongodb_client = MongoDBClient()

