"""
웹 크롤링 및 벡터 DB 저장 모듈
"""
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from openai import AsyncOpenAI
import httpx
from bs4 import BeautifulSoup
import hashlib
from typing import List, Dict
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
# 루트 로거로 전파되도록 설정
logger.propagate = True
logger.handlers.clear()

class VectorStore:
    """MongoDB Atlas 벡터 저장소"""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        
    async def connect(self):
        """MongoDB 연결"""
        try:
            connection_string = os.getenv("MONGODB_URI")
            database_name = os.getenv("MONGODB_DATABASE", "chatbot_db")
            
            if not connection_string:
                logger.error("MONGODB_URI 환경변수가 설정되지 않았습니다.")
                return False
            
            self.client = AsyncIOMotorClient(connection_string, serverSelectionTimeoutMS=5000)
            await self.client.admin.command('ping')
            
            self.db = self.client[database_name]
            self.collection = self.db["knowledge_base"]
            
            logger.info("MongoDB Atlas 벡터 DB 연결 성공")
            return True
            
        except Exception as e:
            logger.error(f"MongoDB 연결 실패: {e}")
            return False
    
    async def disconnect(self):
        """MongoDB 연결 해제"""
        if self.client:
            self.client.close()
    
    async def fetch_web_content(self, url: str) -> str:
        """웹 페이지 내용 가져오기"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 불필요한 태그 제거
                for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()
                
                # 텍스트 추출
                text = soup.get_text(separator='\n', strip=True)
                
                # 여러 공백/줄바꿈 정리
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                cleaned_text = '\n'.join(lines)
                
                return cleaned_text
                
        except Exception as e:
            logger.error(f"웹 페이지 가져오기 실패 ({url}): {e}")
            return ""
    
    def split_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """텍스트를 청크로 분할"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # 마지막 청크인 경우
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            # 문장 경계 찾기 (줄바꿈 또는 마침표)
            if '\n\n' in text[start:end]:
                # 이중 줄바꿈에서 자르기
                last_break = text.rfind('\n\n', start, end)
                if last_break != -1:
                    end = last_break + 2
            elif '\n' in text[start:end]:
                # 단일 줄바꿈에서 자르기
                last_break = text.rfind('\n', start, end)
                if last_break != -1:
                    end = last_break + 1
            elif '.' in text[start:end]:
                # 마침표에서 자르기
                last_dot = text.rfind('.', start, end)
                if last_dot != -1:
                    end = last_dot + 1
            
            chunks.append(text[start:end].strip())
            start = end - overlap  # 오버랩 적용
        
        return chunks
    
    async def create_embedding(self, text: str) -> List[float]:
        """텍스트 임베딩 생성"""
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            return []
    
    async def store_documents(self, url: str, documents: List[Dict[str, str]]):
        """문서들을 벡터 DB에 저장"""
        if self.collection is None:
            logger.error("MongoDB가 연결되지 않았습니다.")
            return
        
        stored_count = 0
        
        for doc in documents:
            try:
                # 임베딩 생성
                embedding = await self.create_embedding(doc['text'])
                if not embedding:
                    continue
                
                # 문서 ID 생성 (텍스트 해시)
                doc_id = hashlib.md5(f"{url}_{doc['text']}".encode()).hexdigest()
                
                # MongoDB에 저장
                document = {
                    "_id": doc_id,
                    "text": doc['text'],
                    "source": url,
                    "metadata": doc.get('metadata', {}),
                    "embedding": embedding,
                    "created_at": os.getenv("TZ", "UTC")
                }
                
                # 기존 문서가 있으면 업데이트, 없으면 삽입
                await self.collection.update_one(
                    {"_id": doc_id},
                    {"$set": document},
                    upsert=True
                )
                
                stored_count += 1
                logger.info(f"문서 저장 완료: {doc_id[:8]}...")
                
            except Exception as e:
                logger.error(f"문서 저장 실패: {e}")
                continue
        
        logger.info(f"총 {stored_count}개 문서 저장 완료")
    
    async def crawl_and_store(self, url: str):
        """웹 페이지를 크롤링하고 벡터 DB에 저장"""
        logger.info(f"웹 페이지 크롤링 시작: {url}")
        
        # 웹 페이지 내용 가져오기
        content = await self.fetch_web_content(url)
        if not content:
            logger.error("웹 페이지 내용을 가져올 수 없습니다.")
            return
        
        logger.info(f"크롤링된 텍스트 길이: {len(content)} 문자")
        
        # 텍스트 분할
        chunks = self.split_text(content, chunk_size=1000, overlap=200)
        logger.info(f"총 {len(chunks)}개의 청크로 분할됨")
        
        # 문서 리스트 생성
        documents = [
            {
                "text": chunk,
                "metadata": {
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
            }
            for i, chunk in enumerate(chunks)
        ]
        
        # 벡터 DB에 저장
        await self.store_documents(url, documents)
        
        logger.info("크롤링 및 저장 완료!")
    
    async def search(self, query: str, limit: int = 5) -> List[Dict]:
        """벡터 검색"""
        if self.collection is None:
            logger.error("MongoDB가 연결되지 않았습니다.")
            return []
        
        try:
            # 쿼리 임베딩 생성
            query_embedding = await self.create_embedding(query)
            if not query_embedding:
                return []
            
            # Atlas Vector Search 사용
            # 주의: Atlas Vector Search는 $vectorSearch aggregation pipeline을 사용합니다
            # 먼저 일반 검색으로 시도하고, 실패하면 대체 방법 사용
            try:
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": "vector_index",
                            "path": "embedding",
                            "queryVector": query_embedding,
                            "numCandidates": limit * 10,  # 검색 후보 수 (limit보다 크게)
                            "limit": limit
                        }
                    },
                    {
                        "$project": {
                            "_id": 1,
                            "text": 1,
                            "source": 1,
                            "metadata": 1,
                            "score": {"$meta": "vectorSearchScore"}
                        }
                    }
                ]
                
                results = []
                async for doc in self.collection.aggregate(pipeline):
                    results.append({
                        "text": doc.get("text", ""),
                        "source": doc.get("source", ""),
                        "metadata": doc.get("metadata", {}),
                        "score": doc.get("score", 0.0)
                    })
                
                if results:
                    return results
            except Exception as e:
                logger.warning(f"벡터 검색 파이프라인 실패, 대체 방법 시도: {e}")
            
            # 대체 방법: 코사인 유사도 계산 (Python에서)
            return await self.cosine_similarity_search(query_embedding, limit)
            
        except Exception as e:
            logger.error(f"벡터 검색 실패: {e}")
            # 벡터 인덱스가 없는 경우 대체 검색 (텍스트 검색)
            return await self.fallback_search(query, limit)

    async def cosine_similarity_search(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """코사인 유사도를 사용한 벡터 검색 (대체 방법)"""
        import numpy as np
        
        try:
            # 모든 문서 가져오기 (임베딩이 있는 것만)
            cursor = self.collection.find({"embedding": {"$exists": True}})
            
            documents = []
            async for doc in cursor:
                if doc.get("embedding") and len(doc["embedding"]) == len(query_embedding):
                    documents.append(doc)
            
            if not documents:
                return []
            
            # 코사인 유사도 계산
            query_vec = np.array(query_embedding)
            similarities = []
            
            for doc in documents:
                doc_vec = np.array(doc["embedding"])
                # 코사인 유사도 계산
                dot_product = np.dot(query_vec, doc_vec)
                norm_product = np.linalg.norm(query_vec) * np.linalg.norm(doc_vec)
                if norm_product > 0:
                    similarity = dot_product / norm_product
                    similarities.append((similarity, doc))
            
            # 유사도 기준으로 정렬
            similarities.sort(key=lambda x: x[0], reverse=True)
            
            # 상위 limit개 반환
            results = []
            for score, doc in similarities[:limit]:
                results.append({
                    "text": doc.get("text", ""),
                    "source": doc.get("source", ""),
                    "metadata": doc.get("metadata", {}),
                    "score": float(score)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"코사인 유사도 검색 실패: {e}")
            return []
    
    async def fallback_search(self, query: str, limit: int = 5) -> List[Dict]:
        """벡터 검색이 불가능한 경우 대체 텍스트 검색"""
        try:
            cursor = self.collection.find(
                {"$text": {"$search": query}},
                {"score": {"$meta": "textScore"}}
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)
            
            results = []
            async for doc in cursor:
                results.append({
                    "text": doc.get("text", ""),
                    "source": doc.get("source", ""),
                    "metadata": doc.get("metadata", {}),
                    "score": doc.get("score", 0.0)
                })
            
            return results
        except Exception as e:
            logger.error(f"대체 검색 실패: {e}")
            return []

# 전역 인스턴스
vector_store = VectorStore()

