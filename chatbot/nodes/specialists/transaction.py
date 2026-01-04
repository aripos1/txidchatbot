"""
Transaction Specialist 노드 - 트랜잭션 조회
"""
import os
import sys
import logging
from pathlib import Path
import httpx
from langchain_core.messages import AIMessage
from langsmith import traceable

from ...models import ChatState
from ...utils import (
    ensure_logger_setup,
    extract_user_message,
    detect_transaction_hash,
)

logger = logging.getLogger(__name__)


@traceable(name="transaction_specialist", run_type="chain")
async def transaction_specialist(state: ChatState):
    """Transaction Specialist: 트랜잭션 조회"""
    
    print("="*60, file=sys.stdout, flush=True)
    print("Transaction Specialist 시작", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    ensure_logger_setup()
    logger.info("Transaction Specialist 시작")
    
    tx_hash = state.get("transaction_hash")
    logger.info(f"Transaction Specialist - state에서 가져온 transaction_hash: {tx_hash[:20] if tx_hash else 'None'}...")
    
    if not tx_hash:
        user_message = extract_user_message(state)
        logger.info(f"Transaction Specialist - 사용자 메시지 전체 길이: {len(user_message)}자")
        tx_hash = detect_transaction_hash(user_message)
        logger.info(f"Transaction Specialist - 추출된 해시: {tx_hash if tx_hash else 'None'}")
    
    if not tx_hash:
        logger.warning("트랜잭션 해시를 찾을 수 없음")
        user_message = extract_user_message(state)
        return {"messages": [AIMessage(content=f"트랜잭션 해시를 찾을 수 없습니다. 입력하신 내용: {user_message[:100]}...\n\n트랜잭션 해시(64자 hex 또는 Base64 형식)를 입력해주세요.")]}
    
    try:
        # 트랜잭션 조회 방법 결정
        use_api = os.getenv("USE_TRANSACTION_API", "false").lower() == "true"
        api_base_url = os.getenv("TRANSACTION_API_URL", "http://localhost:8000")
        
        logger.info(f"트랜잭션 조회 시작: {tx_hash[:20]}...")
        
        if use_api:
            # API를 통한 트랜잭션 조회
            api_url = f"{api_base_url}/api/tx/{tx_hash}"
            logger.info(f"트랜잭션 API 호출: {api_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(api_url)
                response.raise_for_status()
                api_result = response.json()
                
                if api_result.get("found"):
                    tx_result = api_result.get("results", [])
                else:
                    tx_result = []
                    logger.warning(f"API에서 트랜잭션을 찾지 못함: {api_result.get('message', 'Unknown error')}")
        else:
            # 직접 함수 호출
            sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
            from src.services.transaction_service import detect_transaction
            tx_result = await detect_transaction(tx_hash)
        
        if tx_result:
            # 트랜잭션 결과 포맷팅
            result_text = f"트랜잭션 해시: {tx_hash}\n\n"
            
            if isinstance(tx_result, list) and len(tx_result) > 0:
                result_text += f"✅ {len(tx_result)}개 체인에서 트랜잭션을 찾았습니다:\n\n"
                
                for idx, result in enumerate(tx_result, 1):
                    chain_name = result.get("chain", "알 수 없음")
                    chain_symbol = result.get("symbol", "")
                    
                    result_text += f"━━━ [{idx}] {chain_name} ({chain_symbol}) ━━━\n"
                    result_text += f"상태: {result.get('status', '알 수 없음')}\n"
                    
                    if result.get("from"):
                        result_text += f"보낸 주소: {result.get('from')}\n"
                    if result.get("to"):
                        result_text += f"받은 주소: {result.get('to')}\n"
                    if result.get("value") is not None:
                        value = result.get("value")
                        result_text += f"금액: {value:,.8f} {chain_symbol}\n"
                    if result.get("blockNumber"):
                        result_text += f"블록 번호: {result.get('blockNumber')}\n"
                    if result.get("explorer"):
                        explorer_url = f"{result.get('explorer')}{result.get('txid', tx_hash)}"
                        result_text += f"블록 탐색기: {explorer_url}\n"
                    
                    result_text += "\n"
            else:
                result = tx_result[0] if isinstance(tx_result, list) else tx_result
                chain_name = result.get("chain", "알 수 없음")
                chain_symbol = result.get("symbol", "")
                
                result_text += f"✅ {chain_name} ({chain_symbol})에서 트랜잭션을 찾았습니다:\n\n"
                result_text += f"상태: {result.get('status', '알 수 없음')}\n"
                
                if result.get("from"):
                    result_text += f"보낸 주소: {result.get('from')}\n"
                if result.get("to"):
                    result_text += f"받은 주소: {result.get('to')}\n"
                if result.get("value") is not None:
                    value = result.get("value")
                    result_text += f"금액: {value:,.8f} {chain_symbol}\n"
                if result.get("blockNumber"):
                    result_text += f"블록 번호: {result.get('blockNumber')}\n"
                if result.get("explorer"):
                    explorer_url = f"{result.get('explorer')}{result.get('txid', tx_hash)}"
                    result_text += f"블록 탐색기: {explorer_url}\n"
            
            logger.info(f"Transaction Specialist 완료: {len(tx_result) if isinstance(tx_result, list) else 1}개 결과")
            print("="*60, file=sys.stdout, flush=True)
            
            return {
                "messages": [AIMessage(content=result_text)],
                "transaction_results": tx_result
            }
        else:
            return {"messages": [AIMessage(content=f"트랜잭션 해시 '{tx_hash}'에 대한 조회 결과를 찾을 수 없습니다.\n\n지원되는 모든 체인에서 조회했지만 결과를 찾지 못했습니다.")]}
    except Exception as e:
        logger.error(f"트랜잭션 조회 실패: {e}", exc_info=True)
        return {"messages": [AIMessage(content=f"트랜잭션 조회 중 오류가 발생했습니다: {str(e)}\n\n지원되는 체인: Bitcoin, Ethereum, BNB Smart Chain, Polygon, Tron, Arbitrum, Optimism, Solana, TON 등 31개 체인")]}

