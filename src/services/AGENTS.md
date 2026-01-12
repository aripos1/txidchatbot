# 트랜잭션 서비스 모듈 컨텍스트

## Module Context

이 모듈은 31개 블록체인 네트워크의 트랜잭션 조회 서비스를 구현합니다.

**주요 컴포넌트:**

- **Transaction Service**: `transaction_service.py` - 트랜잭션 해시 감지 및 멀티체인 조회
- **Chain Configs**: `chain_configs.py` - 31개 체인 설정 (RPC URL, Explorer URL 등)
- **Cache**: `cache.py` - 트랜잭션 조회 결과 캐싱

**의존성 관계:**

- `transaction_service.py` → `chain_configs.py` (체인 설정 참조)
- `transaction_service.py` → `cache.py` (캐싱 사용)
- `main.py` → `transaction_service.py` (API 엔드포인트에서 호출)

## Tech Stack & Constraints

### 필수 라이브러리

- **HTTPX**: 0.25.1+ (비동기 HTTP 클라이언트, 필수)
- **Pydantic**: 2.0.0+ (데이터 검증)

### 아키텍처 제약

1. **비동기 처리**: 모든 HTTP 요청은 `httpx.AsyncClient()` 사용 (동기 `requests` 사용 금지).
2. **트랜잭션 해시 감지**: 자동으로 트랜잭션 해시를 감지하고 적절한 체인을 선택.
3. **캐싱**: 동일한 트랜잭션 해시는 캐시에서 우선 조회 (성능 최적화).

### 사용 제한

- **절대 사용 금지**: `requests` 라이브러리 (비동기 처리 불가).
- **권장하지 않음**: 동기 HTTP 클라이언트 사용.
- **필수**: `httpx.AsyncClient()` 사용.

## Implementation Patterns

### 새 체인 추가 패턴

**1. `chain_configs.py`에 체인 설정 추가:**

```python
CHAIN_CONFIGS = {
    # 기존 체인들...
    
    "new_chain": {
        "name": "New Chain",
        "symbol": "NEW",
        "rpc_url": "https://rpc.newchain.com",
        "explorer": "https://explorer.newchain.com/tx/",
        "api_key": os.getenv("NEW_CHAIN_API_KEY"),  # 필요 시
    }
}
```

**2. 트랜잭션 해시 패턴 추가 (필요 시):**

`transaction_service.py`의 `detect_transaction()` 함수에서 새 체인의 해시 패턴을 추가하세요.

### 트랜잭션 조회 패턴

**비동기 HTTP 요청:**

```python
import httpx

async def fetch_transaction(chain_config: dict, tx_hash: str):
    """트랜잭션 조회"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                chain_config["rpc_url"],
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getTransactionByHash",
                    "params": [tx_hash],
                    "id": 1
                }
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.warning(f"체인 {chain_config['name']} 타임아웃")
            return None
        except Exception as e:
            logger.error(f"체인 {chain_config['name']} 조회 실패: {e}")
            return None
```

### 캐싱 패턴

**캐시 사용:**

```python
from src.services.cache import get_cached_result, set_cached_result

# 캐시에서 조회
cached = await get_cached_result(tx_hash)
if cached:
    return cached

# 실제 조회
result = await fetch_transaction(chain_config, tx_hash)

# 캐시에 저장
await set_cached_result(tx_hash, result)

return result
```

## Testing Strategy

**테스트 명령어:**

```bash
# 트랜잭션 서비스 테스트
python -m pytest tests/test_transaction_service.py
```

**테스트 작성 패턴:**

- 트랜잭션 해시 감지 테스트 (다양한 체인).
- 멀티체인 조회 테스트.
- 캐싱 동작 테스트.
- HTTP 타임아웃 및 에러 처리 테스트.

**로컬 테스트 환경:**

1. 테스트용 트랜잭션 해시 준비.
2. RPC URL 접근 가능 여부 확인 (일부 체인은 API 키 필요).

## Local Golden Rules

### 이 모듈에서 범하기 쉬운 실수

**1. 동기 HTTP 클라이언트 사용:**

- **잘못된 예**: `requests.get()` (동기)
- **올바른 예**: `httpx.AsyncClient().get()` (비동기)

**2. 타임아웃 처리 누락:**

- **잘못된 예**: 타임아웃 없이 HTTP 요청 → 서버 블로킹
- **올바른 예**: `httpx.AsyncClient(timeout=10.0)` 설정

**3. 에러 처리 부족:**

- **잘못된 예**: HTTP 오류 발생 시 전체 프로세스 중단
- **올바른 예**: 개별 체인 실패는 무시하고 다른 체인 계속 조회

**4. 캐싱 누락:**

- **잘못된 예**: 매번 모든 체인에 요청 → 성능 저하
- **올바른 예**: 캐시에서 우선 조회, 없으면 실제 요청 후 캐시 저장

**5. 체인 설정 하드코딩:**

- **잘못된 예**: RPC URL을 코드에 직접 작성
- **올바른 예**: `chain_configs.py`에서 중앙 관리

### 권장 사항

- 새 체인 추가 시 `chain_configs.py`만 수정하세요.
- 트랜잭션 조회는 항상 비동기로 처리하세요.
- 타임아웃을 적절히 설정하세요 (기본 10초).
- 에러 발생 시 로깅을 수행하고 계속 진행하세요.
- 캐싱을 활용하여 성능을 최적화하세요.
