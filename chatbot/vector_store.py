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
from typing import List, Dict, Optional
import logging
from datetime import datetime
from dotenv import load_dotenv

# 상대 경로 import를 위해 현재 디렉토리 확인
try:
    from .configuration import config
except ImportError:
    from chatbot.configuration import config

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
            self.collection = self.db["knowledge_base"]
            
            logger.info("MongoDB Atlas 벡터 DB 연결 성공")
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"MongoDB 벡터 DB 연결 타임아웃 (5초)")
            return False
        except asyncio.CancelledError:
            logger.warning(f"MongoDB 벡터 DB 연결이 취소되었습니다")
            return False
        except ConnectionFailure as e:
            logger.error(f"MongoDB 벡터 DB 연결 실패: {e}")
            return False
        except Exception as e:
            logger.error(f"MongoDB 벡터 DB 연결 오류: {e}")
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
    
    async def search(self, query: str, limit: Optional[int] = None) -> List[Dict]:
        """벡터 검색"""
        if self.collection is None:
            logger.error("MongoDB가 연결되지 않았습니다.")
            return []
        
        # limit이 지정되지 않으면 설정값 사용
        if limit is None:
            limit = config.VECTOR_SEARCH_LIMIT
        
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
    
    async def keyword_search(self, query: str, limit: int = 5) -> List[Dict]:
        """키워드 검색(BM25/Lexical) - Atlas Search 사용"""
        if self.collection is None:
            logger.error("MongoDB가 연결되지 않았습니다.")
            return []
        
        try:
            # Atlas Search 사용 ($search aggregation stage)
            pipeline = [
                {
                    "$search": {
                        "index": "text_index",  # Atlas Search 인덱스 이름
                        "text": {
                            "query": query,
                            "path": {
                                "wildcard": "*"  # 모든 필드 검색 (answer, question, source)
                            }
                        }
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "text": 1,
                        "source": 1,
                        "metadata": 1,
                        "score": {"$meta": "searchScore"}
                    }
                },
                {
                    "$limit": limit
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
            logger.warning(f"Atlas Search 키워드 검색 실패, 대체 방법 시도: {e}")
        
        # 대체 방법: MongoDB 표준 $text 검색 (Atlas Search 실패 시)
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
            logger.warning(f"키워드 검색 대체 방법도 실패: {e}")
            return []
    
    async def hybrid_search(
        self, 
        query: str, 
        limit: Optional[int] = None,
        use_rrf: bool = False
    ) -> List[Dict]:
        """하이브리드 검색: 벡터 검색 + 키워드 검색 결합"""
        if self.collection is None:
            logger.error("MongoDB가 연결되지 않았습니다.")
            return []
        
        # 설정값 가져오기
        k_weight = config.HYBRID_K_WEIGHT
        s_weight = config.HYBRID_S_WEIGHT
        rrf_k = config.RRF_K
        final_limit = limit or config.FINAL_TOP_K
        
        # 각 검색 수행 (충분한 결과를 위해 limit * 2로 검색)
        search_limit = final_limit * 2
        
        # 벡터 검색 (시맨틱 검색)
        vector_results = await self.search(query, limit=search_limit)
        
        # 키워드 검색
        keyword_results = await self.keyword_search(query, limit=search_limit)
        
        # 결과가 없으면 벡터 검색 결과만 반환
        if not vector_results and not keyword_results:
            return []
        if not keyword_results:
            return vector_results[:final_limit]
        if not vector_results:
            return keyword_results[:final_limit]
        
        # 결과 통합 (RRF 또는 가중치 결합)
        if use_rrf:
            # RRF(Reciprocal Rank Fusion) 사용
            combined_results = self._combine_results_rrf(
                vector_results, keyword_results, rrf_k
            )
        else:
            # 가중치 결합 사용
            combined_results = self._combine_results_weighted(
                vector_results, keyword_results, k_weight, s_weight
            )
        
        # 최종 결과 반환
        final_results = combined_results[:final_limit]
        logger.info(f"하이브리드 검색 완료: 벡터 {len(vector_results)}개, 키워드 {len(keyword_results)}개 → 최종 {len(final_results)}개")
        
        return final_results
    
    def _combine_results_rrf(
        self, 
        vector_results: List[Dict], 
        keyword_results: List[Dict], 
        rrf_k: int
    ) -> List[Dict]:
        """RRF(Reciprocal Rank Fusion)를 사용한 결과 결합"""
        # 문서 ID를 키로 하는 딕셔너리 생성
        doc_scores: Dict[str, Dict] = {}
        
        # 벡터 검색 결과 점수 계산
        for rank, result in enumerate(vector_results, start=1):
            doc_id = result.get("source", "") + "|" + result.get("text", "")[:50]
            rrf_score = 1.0 / (rrf_k + rank)
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    "text": result.get("text", ""),
                    "source": result.get("source", ""),
                    "metadata": result.get("metadata", {}),
                    "score": 0.0
                }
            doc_scores[doc_id]["score"] += rrf_score
        
        # 키워드 검색 결과 점수 계산
        for rank, result in enumerate(keyword_results, start=1):
            doc_id = result.get("source", "") + "|" + result.get("text", "")[:50]
            rrf_score = 1.0 / (rrf_k + rank)
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    "text": result.get("text", ""),
                    "source": result.get("source", ""),
                    "metadata": result.get("metadata", {}),
                    "score": 0.0
                }
            doc_scores[doc_id]["score"] += rrf_score
        
        # 점수 기준으로 정렬
        combined = list(doc_scores.values())
        combined.sort(key=lambda x: x["score"], reverse=True)
        
        return combined
    
    def _combine_results_weighted(
        self, 
        vector_results: List[Dict], 
        keyword_results: List[Dict], 
        k_weight: float, 
        s_weight: float
    ) -> List[Dict]:
        """가중치 결합을 사용한 결과 결합"""
        # 문서 ID를 키로 하는 딕셔너리 생성
        doc_scores: Dict[str, Dict] = {}
        
        # 1. 벡터 검색 점수 처리
        # 벡터 검색 점수(코사인 유사도)는 이미 0~1 범위이므로 정규화하지 않고 원본 점수에 가중치만 적용
        for result in vector_results:
            doc_id = result.get("source", "") + "|" + result.get("text", "")[:50]
            # 벡터 검색 점수는 이미 0~1 범위이므로 정규화 없이 가중치만 곱함
            weighted_score = result.get("score", 0.0) * s_weight
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    "text": result.get("text", ""),
                    "source": result.get("source", ""),
                    "metadata": result.get("metadata", {}),
                    "score": 0.0
                }
            doc_scores[doc_id]["score"] += weighted_score
        
        # 2. 키워드 검색 점수 처리
        # 키워드 검색 점수(BM25)는 보통 0~20 이상일 수 있으므로 정규화 필요
        # 하지만 결과가 적거나 점수가 낮을 때 과도한 정규화를 방지하기 위해 절대 평가 요소 도입
        max_keyword_score = max([r.get("score", 0.0) for r in keyword_results], default=1.0)
        
        if max_keyword_score > 0:
            # 키워드 검색 결과가 적거나 점수가 낮을 때 과도한 정규화 방지
            # 최소 정규화 기준값 설정 (BM25 점수가 10점 미만이면 강제로 10점 기준으로 정규화)
            MIN_KEYWORD_SCORE_THRESHOLD = 10.0  # 환경에 따라 조정 가능
            
            if max_keyword_score < MIN_KEYWORD_SCORE_THRESHOLD:
                # 최고 점수가 너무 낮으면 절대 평가 기준 사용
                normalization_factor = MIN_KEYWORD_SCORE_THRESHOLD
                logger.debug(f"키워드 검색 최고 점수가 낮음 ({max_keyword_score:.2f} < {MIN_KEYWORD_SCORE_THRESHOLD}), 절대 평가 기준 사용")
            else:
                # 정상 범위면 최고 점수로 정규화
                normalization_factor = max_keyword_score
            
            # 키워드 검색 결과 점수 계산 (정규화 후 가중치 적용)
            for result in keyword_results:
                doc_id = result.get("source", "") + "|" + result.get("text", "")[:50]
                normalized_score = result.get("score", 0.0) / normalization_factor
                # 정규화 후 1.0을 초과하지 않도록 제한
                normalized_score = min(normalized_score, 1.0)
                weighted_score = normalized_score * k_weight
                
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        "text": result.get("text", ""),
                        "source": result.get("source", ""),
                        "metadata": result.get("metadata", {}),
                        "score": 0.0
                    }
                doc_scores[doc_id]["score"] += weighted_score
        
        # 점수 기준으로 정렬
        combined = list(doc_scores.values())
        combined.sort(key=lambda x: x["score"], reverse=True)
        
        # 점수 범위 확인 로그 (디버깅용)
        if combined:
            max_combined_score = combined[0]["score"]
            logger.info(f"가중치 결합 최고 점수: {max_combined_score:.4f} (가중치: 벡터={s_weight}, 키워드={k_weight}, 벡터 결과={len(vector_results)}개, 키워드 결과={len(keyword_results)}개)")
            if max_combined_score > 1.0:
                logger.warning(f"가중치 결합 점수가 1.0을 초과: {max_combined_score:.4f} (가중치: 벡터={s_weight}, 키워드={k_weight})")
        
        return combined
    
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

