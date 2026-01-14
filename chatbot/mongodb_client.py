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
            self.admin_collection = self.db["admin_settings"]
            
            # 인덱스 생성 (성능 최적화)
            await self.chat_collection.create_index("session_id")
            await self.chat_collection.create_index("created_at")
            await self.inquiry_collection.create_index("email")
            await self.inquiry_collection.create_index("created_at")
            await self.inquiry_collection.create_index("status")
            await self.admin_collection.create_index("key", unique=True)
            
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
        """대화 기록 조회 (시간순 정렬)"""
        if self.chat_collection is None:
            logger.warning(f"[MongoDB] chat_collection이 None입니다. session_id: {session_id}")
            return []
        
        try:
            logger.info(f"[MongoDB] 대화 기록 조회 시작 - session_id: {session_id}, limit: {limit}")
            
            # created_at 기준으로 오름차순 정렬, 같으면 _id로 정렬 (시간순 보장)
            cursor = self.chat_collection.find(
                {"session_id": session_id}
            ).sort([("created_at", 1), ("_id", 1)]).limit(limit)
            
            messages = await cursor.to_list(length=limit)
            logger.info(f"[MongoDB] 조회 완료 - 메시지 개수: {len(messages)}")
            
            if messages:
                # 모든 메시지의 role 확인
                roles = [msg.get('role', 'unknown') for msg in messages]
                user_count = sum(1 for r in roles if r == 'user')
                assistant_count = sum(1 for r in roles if r == 'assistant')
                logger.info(f"[MongoDB] 조회된 메시지 role 목록: {roles}")
                logger.info(f"[MongoDB] user 메시지 개수: {user_count}, assistant 메시지 개수: {assistant_count}")
                
                logger.info(f"[MongoDB] 첫 번째 메시지: role={messages[0].get('role')}, created_at={messages[0].get('created_at')}, content 길이={len(messages[0].get('content', ''))}")
                logger.info(f"[MongoDB] 마지막 메시지: role={messages[-1].get('role')}, created_at={messages[-1].get('created_at')}, content 길이={len(messages[-1].get('content', ''))}")
            else:
                logger.warning(f"[MongoDB] 조회된 메시지가 없습니다. session_id: {session_id}")
            
            return messages
        except Exception as e:
            logger.error(f"[MongoDB] 대화 기록 조회 실패: {e}", exc_info=True)
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
    
    async def get_inquiry_statistics(self):
        """문의사항 상세 통계 조회"""
        if self.inquiry_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return {}
        
        try:
            from datetime import timedelta
            from collections import defaultdict
            
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            # 전체 문의사항 조회
            all_inquiries = await self.inquiry_collection.find({}).to_list(length=None)
            
            # 기본 통계
            stats = {
                "total": len(all_inquiries),
                "by_status": defaultdict(int),
                "by_category": defaultdict(int),
                "recent_7_days": 0,
                "recent_30_days": 0,
                "daily_counts": defaultdict(int),  # 최근 7일 일별 카운트
                "hourly_distribution": defaultdict(int),  # 시간대별 분포 (0-23)
                "avg_response_time_hours": 0,  # 평균 응답 시간 (시간 단위)
                "response_times": []  # 응답 시간 목록
            }
            
            # 통계 계산
            total_response_time = 0
            response_count = 0
            
            for inquiry in all_inquiries:
                created_at = inquiry.get("created_at")
                updated_at = inquiry.get("updated_at")
                status = inquiry.get("status", "pending")
                category = inquiry.get("category", "기타")
                
                # 상태별 통계
                stats["by_status"][status] += 1
                
                # 카테고리별 통계
                stats["by_category"][category] += 1
                
                if created_at:
                    # 최근 7일, 30일 통계
                    if isinstance(created_at, datetime):
                        if created_at >= week_ago:
                            stats["recent_7_days"] += 1
                        if created_at >= month_ago:
                            stats["recent_30_days"] += 1
                        
                        # 일별 카운트 (최근 7일)
                        if created_at >= week_ago:
                            date_key = created_at.strftime("%Y-%m-%d")
                            stats["daily_counts"][date_key] += 1
                        
                        # 시간대별 분포
                        hour = created_at.hour
                        stats["hourly_distribution"][hour] += 1
                    
                    # 응답 시간 계산 (답변 완료된 경우)
                    if status in ["replied", "closed"] and updated_at and created_at:
                        if isinstance(created_at, datetime) and isinstance(updated_at, datetime):
                            response_time = (updated_at - created_at).total_seconds() / 3600  # 시간 단위
                            stats["response_times"].append(response_time)
                            total_response_time += response_time
                            response_count += 1
            
            # 평균 응답 시간 계산
            if response_count > 0:
                stats["avg_response_time_hours"] = round(total_response_time / response_count, 2)
            
            # 딕셔너리를 일반 dict로 변환
            stats["by_status"] = dict(stats["by_status"])
            stats["by_category"] = dict(stats["by_category"])
            stats["daily_counts"] = dict(stats["daily_counts"])
            stats["hourly_distribution"] = dict(stats["hourly_distribution"])
            
            # 일별 카운트를 최근 7일 순서대로 정렬
            sorted_daily = []
            for i in range(7):
                date = (today - timedelta(days=6-i)).strftime("%Y-%m-%d")
                sorted_daily.append({
                    "date": date,
                    "count": stats["daily_counts"].get(date, 0)
                })
            stats["daily_counts"] = sorted_daily
            
            return stats
        except Exception as e:
            logger.error(f"문의사항 통계 조회 실패: {e}", exc_info=True)
            return {}
    
    async def get_chat_statistics(self):
        """채팅 상세 통계 조회"""
        if self.chat_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return {}
        
        try:
            from datetime import timedelta
            from collections import defaultdict
            
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            # 전체 메시지 조회 (시간순 정렬)
            all_messages = await self.chat_collection.find({}).sort("created_at", 1).to_list(length=None)
            
            # 기본 통계
            stats = {
                "total_messages": len(all_messages),
                "user_messages": 0,
                "assistant_messages": 0,
                "total_sessions": 0,
                "recent_7_days": 0,
                "recent_30_days": 0,
                "daily_counts": defaultdict(int),  # 최근 7일 일별 카운트
                "hourly_distribution": defaultdict(int),  # 시간대별 분포 (0-23)
                "avg_messages_per_session": 0,  # 세션당 평균 메시지 수
                "sessions_by_day": defaultdict(int)  # 일별 세션 수
            }
            
            # 세션별 메시지 수 추적
            session_message_counts = defaultdict(int)
            session_first_dates = {}  # 세션별 첫 메시지 날짜 추적
            
            for message in all_messages:
                role = message.get("role", "user")
                created_at = message.get("created_at")
                session_id = message.get("session_id", "unknown")
                
                # 역할별 통계
                if role == "user":
                    stats["user_messages"] += 1
                elif role == "assistant":
                    stats["assistant_messages"] += 1
                
                # 세션별 메시지 수 카운트
                session_message_counts[session_id] += 1
                
                if created_at:
                    # 최근 7일, 30일 통계
                    if isinstance(created_at, datetime):
                        if created_at >= week_ago:
                            stats["recent_7_days"] += 1
                        if created_at >= month_ago:
                            stats["recent_30_days"] += 1
                        
                        # 일별 카운트 (최근 7일)
                        if created_at >= week_ago:
                            date_key = created_at.strftime("%Y-%m-%d")
                            stats["daily_counts"][date_key] += 1
                        
                        # 시간대별 분포
                        hour = created_at.hour
                        stats["hourly_distribution"][hour] += 1
                        
                        # 세션 생성 날짜 추적 (각 세션의 첫 메시지 날짜)
                        if session_id not in session_first_dates:
                            session_date_key = created_at.strftime("%Y-%m-%d")
                            stats["sessions_by_day"][session_date_key] += 1
                            session_first_dates[session_id] = session_date_key
            
            # 세션 수 계산
            stats["total_sessions"] = len(session_message_counts)
            
            # 세션당 평균 메시지 수 계산
            if stats["total_sessions"] > 0:
                total_session_messages = sum(session_message_counts.values())
                stats["avg_messages_per_session"] = round(total_session_messages / stats["total_sessions"], 2)
            
            # 딕셔너리를 일반 dict로 변환
            stats["daily_counts"] = dict(stats["daily_counts"])
            stats["hourly_distribution"] = dict(stats["hourly_distribution"])
            stats["sessions_by_day"] = dict(stats["sessions_by_day"])
            
            # 일별 카운트를 최근 7일 순서대로 정렬
            sorted_daily = []
            for i in range(7):
                date = (today - timedelta(days=6-i)).strftime("%Y-%m-%d")
                sorted_daily.append({
                    "date": date,
                    "count": stats["daily_counts"].get(date, 0)
                })
            stats["daily_counts"] = sorted_daily
            
            # 일별 세션 수를 최근 7일 순서대로 정렬
            sorted_sessions = []
            for i in range(7):
                date = (today - timedelta(days=6-i)).strftime("%Y-%m-%d")
                sorted_sessions.append({
                    "date": date,
                    "count": stats["sessions_by_day"].get(date, 0)
                })
            stats["sessions_by_day"] = sorted_sessions
            
            return stats
        except Exception as e:
            logger.error(f"채팅 통계 조회 실패: {e}", exc_info=True)
            return {}
    
    async def get_chat_content_statistics(self, use_ai_analysis: bool = True):
        """채팅 내용 분석 통계 조회 (AI 분석 포함)"""
        if self.chat_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return {}
        
        try:
            import re
            from collections import defaultdict, Counter
            import json
            
            # 사용자 메시지만 조회
            user_messages = await self.chat_collection.find({"role": "user"}).to_list(length=None)
            
            # 기본 통계
            stats = {
                "total_user_messages": len(user_messages),
                "top_keywords": [],  # 상위 키워드
                "question_types": defaultdict(int),  # 질문 유형별 분포
                "blockchain_networks": defaultdict(int),  # 블록체인 네트워크 언급 빈도
                "topics": defaultdict(int),  # 주제별 분포
                "avg_message_length": 0,  # 평균 메시지 길이
                "message_length_distribution": defaultdict(int)  # 메시지 길이 분포
            }
            
            # 블록체인 네트워크 키워드
            blockchain_keywords = {
                "비트코인": ["bitcoin", "btc", "비트코인"],
                "이더리움": ["ethereum", "eth", "이더리움"],
                "바이낸스": ["binance", "bnb", "바이낸스", "bsc"],
                "폴리곤": ["polygon", "matic", "폴리곤"],
                "솔라나": ["solana", "sol", "솔라나"],
                "트론": ["tron", "trx", "트론"],
                "아비트럼": ["arbitrum", "arb", "아비트럼"],
                "옵티미즘": ["optimism", "op", "옵티미즘"],
                "베이스": ["base", "베이스"],
                "아발란체": ["avalanche", "avax", "아발란체"]
            }
            
            # 질문 유형 키워드
            question_type_patterns = {
                "트랜잭션 조회": [r"0x[a-fA-F0-9]{64}", r"트랜잭션", r"txid", r"tx", r"해시", r"거래"],
                "시세 조회": [r"시세", r"가격", r"price", r"현재가", r"시장가", r"코인.*가격", r"얼마"],
                "FAQ": [r"어떻게", r"방법", r"사용법", r"가이드", r"설명", r"뭐야", r"무엇"],
                "일반 대화": [r"안녕", r"반가워", r"고마워", r"감사", r"도와줘", r"help"]
            }
            
            # 전체 텍스트 수집
            all_text = ""
            total_length = 0
            
            for message in user_messages:
                content = message.get("content", "").lower()
                if not content:
                    continue
                
                all_text += " " + content
                content_length = len(content)
                total_length += content_length
                
                # 메시지 길이 분포 (100자 단위)
                length_category = (content_length // 100) * 100
                stats["message_length_distribution"][length_category] += 1
                
                # 질문 유형 분류
                for q_type, patterns in question_type_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            stats["question_types"][q_type] += 1
                            break
                
                # 블록체인 네트워크 언급 확인
                for network, keywords in blockchain_keywords.items():
                    for keyword in keywords:
                        if keyword.lower() in content:
                            stats["blockchain_networks"][network] += 1
                            break
            
            # 평균 메시지 길이
            if len(user_messages) > 0:
                stats["avg_message_length"] = round(total_length / len(user_messages), 1)
            
            # 키워드 추출 (한글, 영문 단어)
            # 불용어 제거
            stopwords = {"은", "는", "이", "가", "을", "를", "의", "에", "에서", "와", "과", "도", "로", "으로", 
                        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
            
            # 한글 단어 추출 (2글자 이상)
            korean_words = re.findall(r'[가-힣]{2,}', all_text)
            # 영문 단어 추출 (3글자 이상)
            english_words = re.findall(r'\b[a-z]{3,}\b', all_text.lower())
            
            # 키워드 빈도 계산
            all_words = korean_words + english_words
            word_freq = Counter([word for word in all_words if word not in stopwords])
            
            # 상위 20개 키워드
            stats["top_keywords"] = [
                {"word": word, "count": count} 
                for word, count in word_freq.most_common(20)
            ]
            
            # 주제별 분류 (키워드 기반)
            topic_keywords = {
                "트랜잭션": ["트랜잭션", "txid", "해시", "거래", "transaction"],
                "시세": ["시세", "가격", "price", "현재가", "시장가"],
                "지갑": ["지갑", "wallet", "주소", "address"],
                "가스": ["가스", "gas", "수수료", "fee"],
                "스마트 컨트랙트": ["스마트", "컨트랙트", "contract", "스마트컨트랙트"],
                "디파이": ["defi", "디파이", "유동성", "liquidity"],
                "NFT": ["nft", "토큰", "token"],
                "스테이킹": ["스테이킹", "staking", "예치"]
            }
            
            for topic, keywords in topic_keywords.items():
                for keyword in keywords:
                    if keyword.lower() in all_text:
                        stats["topics"][topic] += 1
                        break
            
            # 딕셔너리를 일반 dict로 변환
            stats["question_types"] = dict(stats["question_types"])
            stats["blockchain_networks"] = dict(stats["blockchain_networks"])
            stats["topics"] = dict(stats["topics"])
            stats["message_length_distribution"] = dict(stats["message_length_distribution"])
            
            # AI 분석 추가
            if use_ai_analysis:
                try:
                    if len(user_messages) > 0:
                        logger.info(f"AI 분석 시작: {len(user_messages)}개 메시지 분석")
                        from .analyzers.chat_analyzer import analyze_chat_with_ai
                        ai_insights = await analyze_chat_with_ai(user_messages, stats)
                        if ai_insights:
                            stats.update(ai_insights)
                            logger.info("AI 분석 완료")
                        else:
                            logger.warning("AI 분석 결과가 비어있습니다.")
                    else:
                        logger.info("분석할 메시지가 없어 AI 분석을 건너뜁니다.")
                except Exception as ai_error:
                    logger.error(f"AI 분석 실패 (기본 통계는 정상): {ai_error}", exc_info=True)
            
            return stats
        except Exception as e:
            logger.error(f"채팅 내용 통계 조회 실패: {e}", exc_info=True)
            return {}
    
    async def get_admin_password_hash(self) -> Optional[str]:
        """관리자 비밀번호 해시 조회"""
        if self.admin_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return None
        
        try:
            admin_setting = await self.admin_collection.find_one({"key": "password_hash"})
            if admin_setting:
                return admin_setting.get("value")
            return None
        except Exception as e:
            logger.error(f"관리자 비밀번호 조회 실패: {e}")
            return None
    
    async def set_admin_password_hash(self, password_hash: str) -> bool:
        """관리자 비밀번호 해시 저장/업데이트"""
        if self.admin_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return False
        
        try:
            result = await self.admin_collection.update_one(
                {"key": "password_hash"},
                {
                    "$set": {
                        "value": password_hash,
                        "updated_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            return result.acknowledged
        except Exception as e:
            logger.error(f"관리자 비밀번호 저장 실패: {e}")
            return False
    
    async def initialize_admin_password(self, default_password: str) -> bool:
        """관리자 비밀번호 초기화 (없을 경우에만)"""
        if self.admin_collection is None:
            logger.warning("MongoDB가 연결되지 않았습니다.")
            return False
        
        try:
            existing = await self.admin_collection.find_one({"key": "password_hash"})
            if existing:
                logger.info("관리자 비밀번호가 이미 설정되어 있습니다.")
                return True
            
            import bcrypt
            password_hash = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            await self.admin_collection.insert_one({
                "key": "password_hash",
                "value": password_hash,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            logger.info("관리자 비밀번호가 초기화되었습니다.")
            return True
        except Exception as e:
            logger.error(f"관리자 비밀번호 초기화 실패: {e}")
            return False

# 전역 MongoDB 클라이언트 인스턴스
mongodb_client = MongoDBClient()

