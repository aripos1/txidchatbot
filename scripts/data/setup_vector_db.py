"""
MongoDB Atlas 벡터 DB 초기 설정 스크립트
"""
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

load_dotenv()

async def setup_database():
    """데이터베이스와 컬렉션 생성"""
    try:
        # MongoDB 연결
        connection_string = os.getenv("MONGODB_URI")
        database_name = os.getenv("MONGODB_DATABASE", "chatbot_db")
        
        if not connection_string:
            print("❌ MONGODB_URI 환경변수가 설정되지 않았습니다.")
            return False
        
        print("🔄 MongoDB Atlas에 연결 중...")
        client = AsyncIOMotorClient(connection_string, serverSelectionTimeoutMS=5000)
        
        # 연결 테스트
        await client.admin.command('ping')
        print("✅ MongoDB Atlas 연결 성공!")
        
        # 데이터베이스 및 컬렉션 생성
        db = client[database_name]
        collection = db["knowledge_base"]
        
        # 컬렉션이 없으면 생성 (첫 문서 삽입 시 자동 생성됨)
        # 샘플 문서 삽입하여 컬렉션 생성
        await collection.insert_one({
            "_id": "setup_document",
            "text": "Setup document",
            "source": "setup",
            "embedding": [0.0] * 1536  # 더미 임베딩
        })
        
        # 설정 문서 삭제
        await collection.delete_one({"_id": "setup_document"})
        
        print(f"✅ 데이터베이스 '{database_name}' 및 컬렉션 'knowledge_base' 생성 완료!")
        
        # 벡터 검색 인덱스 생성 안내
        print("\n📌 다음 단계:")
        print("1. MongoDB Atlas 웹 콘솔로 이동")
        print("2. Database → 클러스터 선택 → Search 탭")
        print("3. 'Create Search Index' 클릭")
        print("4. JSON Editor 선택")
        print("5. Database: chatbot_db, Collection: knowledge_base 선택")
        print("6. 인덱스 이름: vector_index")
        print("7. 아래 JSON 입력:")
        print("""
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "source"
    }
  ]
}
        """)
        print("8. 'Create Search Index' 클릭 (생성에 몇 분 소요)")
        
        client.close()
        return True
        
    except ConnectionFailure as e:
        print(f"❌ MongoDB 연결 실패: {e}")
        print("연결 문자열과 네트워크 액세스 설정을 확인해주세요.")
        return False
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(setup_database())

