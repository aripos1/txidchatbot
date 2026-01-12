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
    logger.info(f"Transaction Specialist - state에서 가져온 transaction_hash: {tx_hash if tx_hash else 'None'} (길이: {len(tx_hash) if tx_hash else 0}자)")
    
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
        # 기본값을 "true"로 변경하여 웹 UI와 동일한 API 사용
        use_api = os.getenv("USE_TRANSACTION_API", "true").lower() == "true"
        api_base_url = os.getenv("TRANSACTION_API_URL", "http://localhost:8000")
        
        logger.info(f"트랜잭션 조회 시작: {tx_hash[:20]}...")
        logger.info(f"USE_TRANSACTION_API={use_api}, API_BASE_URL={api_base_url}")
        
        if use_api:
            # API를 통한 트랜잭션 조회
            api_url = f"{api_base_url}/api/tx/{tx_hash}"
            logger.info(f"트랜잭션 API 호출: {api_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(api_url)
                response.raise_for_status()
                api_result = response.json()
                
                logger.info(f"API 응답: found={api_result.get('found')}, results 개수={len(api_result.get('results', []))}")
                
                if api_result.get("found"):
                    tx_result = api_result.get("results", [])
                    logger.info(f"API에서 {len(tx_result)}개 결과 반환")
                else:
                    tx_result = []
                    logger.warning(f"API에서 트랜잭션을 찾지 못함: {api_result.get('message', 'Unknown error')}")
        else:
            # 직접 함수 호출
            sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
            from src.services.transaction_service import detect_transaction
            tx_result = await detect_transaction(tx_hash)
            logger.info(f"detect_transaction 반환값 타입: {type(tx_result)}, 값: {tx_result}")
            if isinstance(tx_result, list):
                logger.info(f"detect_transaction 반환 리스트 길이: {len(tx_result)}")
                if len(tx_result) > 0:
                    logger.info(f"첫 번째 결과: {tx_result[0]}")
                else:
                    logger.warning(f"detect_transaction이 빈 리스트를 반환했습니다.")
            else:
                logger.info(f"detect_transaction 반환값 (리스트 아님): {tx_result}")
        
        # 결과 확인: 리스트인 경우 길이 체크, 아닌 경우 truthy 체크
        has_results = False
        if isinstance(tx_result, list):
            has_results = len(tx_result) > 0
            logger.info(f"결과 확인: 리스트 길이={len(tx_result)}, has_results={has_results}")
        elif tx_result:
            has_results = True
            logger.info(f"결과 확인: 리스트가 아닌 값, has_results={has_results}")
        else:
            logger.warning(f"결과 확인: tx_result가 None이거나 빈 값")
        
        if has_results:
            # 트랜잭션 결과 포맷팅
            result_text = f"트랜잭션 해시: {tx_hash}\n\n"
            
            if isinstance(tx_result, list) and len(tx_result) > 0:
                result_text += f"✅ {len(tx_result)}개 체인에서 트랜잭션을 찾았습니다:\n\n"
                
                for idx, result in enumerate(tx_result, 1):
                    chain_name = result.get("chain", "알 수 없음")
                    chain_symbol = result.get("symbol", "")
                    
                    # 디버깅: result의 txid 확인
                    result_txid = result.get('txid')
                    logger.debug(f"[{idx}] {chain_name} - result.txid: {result_txid} (길이: {len(result_txid) if result_txid else 0}자), tx_hash: {tx_hash} (길이: {len(tx_hash) if tx_hash else 0}자)")
                    
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
                        # txid가 있으면 사용, 없으면 원본 tx_hash 사용
                        txid_for_explorer = result_txid if result_txid else tx_hash
                        # explorer URL 끝의 / 제거 후 다시 추가하여 올바른 URL 형식 보장
                        explorer_base = result.get('explorer', '').rstrip('/')
                        explorer_url = f"{explorer_base}/{txid_for_explorer}"
                        # URL 검증
                        expected_length = len(explorer_base) + len(txid_for_explorer)
                        if len(explorer_url) != expected_length:
                            logger.error(f"URL 길이 불일치! 예상: {expected_length}, 실제: {len(explorer_url)}")
                            logger.error(f"explorer_base: '{explorer_base}' (길이: {len(explorer_base)})")
                            logger.error(f"txid_for_explorer: '{txid_for_explorer}' (길이: {len(txid_for_explorer)})")
                            logger.error(f"explorer_url: '{explorer_url}' (길이: {len(explorer_url)})")
                        explorer_line = f"블록 탐색기: {explorer_url}\n"
                        result_text += explorer_line
                        # URL이 제대로 포함되었는지 검증
                        if explorer_url not in explorer_line:
                            logger.error(f"URL이 result_text에 제대로 포함되지 않음! explorer_url='{explorer_url}', explorer_line='{explorer_line}'")
                        # result_text에서 URL 부분 추출하여 검증
                        if "블록 탐색기:" in result_text:
                            extracted_url = result_text.split("블록 탐색기:")[-1].split("\n")[0].strip()
                            if extracted_url != explorer_url:
                                logger.error(f"추출된 URL이 원본과 다름! 원본='{explorer_url}' (길이: {len(explorer_url)}), 추출='{extracted_url}' (길이: {len(extracted_url)})")
                        logger.info(f"탐색기 URL 생성: explorer={result.get('explorer')}, txid={result_txid} (길이: {len(result_txid) if result_txid else 0}), tx_hash={tx_hash} (길이: {len(tx_hash) if tx_hash else 0}), 최종 URL='{explorer_url}' (길이: {len(explorer_url)}), result_text에 추가됨")
                    
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
                    # txid가 있으면 사용, 없으면 원본 tx_hash 사용
                    txid_for_explorer = result.get('txid') or tx_hash
                    # explorer URL 끝의 / 제거 후 다시 추가하여 올바른 URL 형식 보장
                    explorer_base = result.get('explorer', '').rstrip('/')
                    explorer_url = f"{explorer_base}/{txid_for_explorer}"
                    # URL 검증
                    expected_length = len(explorer_base) + len(txid_for_explorer)
                    if len(explorer_url) != expected_length:
                        logger.error(f"URL 길이 불일치! 예상: {expected_length}, 실제: {len(explorer_url)}")
                    explorer_line = f"블록 탐색기: {explorer_url}\n"
                    result_text += explorer_line
                    # URL이 제대로 포함되었는지 검증
                    if explorer_url not in explorer_line:
                        logger.error(f"URL이 result_text에 제대로 포함되지 않음! explorer_url='{explorer_url}', explorer_line='{explorer_line}'")
                    logger.info(f"탐색기 URL 생성: explorer={result.get('explorer')}, txid={result.get('txid')} (길이: {len(result.get('txid')) if result.get('txid') else 0}), tx_hash={tx_hash} (길이: {len(tx_hash) if tx_hash else 0}), 최종 URL='{explorer_url}' (길이: {len(explorer_url)}), result_text에 추가됨")
            
            logger.info(f"Transaction Specialist 완료: {len(tx_result) if isinstance(tx_result, list) else 1}개 결과")
            # 최종 result_text에서 URL 부분 검증
            if "블록 탐색기:" in result_text:
                url_lines = [line for line in result_text.split("\n") if "블록 탐색기:" in line]
                for url_line in url_lines:
                    extracted_url = url_line.split("블록 탐색기:")[-1].strip()
                    logger.info(f"최종 result_text에서 추출된 URL: '{extracted_url}' (길이: {len(extracted_url)})")
            print("="*60, file=sys.stdout, flush=True)
            
            return {
                "messages": [AIMessage(content=result_text)],
                "transaction_results": tx_result
            }
        else:
            logger.warning(f"트랜잭션 조회 결과 없음. tx_result 타입: {type(tx_result)}, 값: {tx_result}")
            return {"messages": [AIMessage(content=f"트랜잭션 해시 '{tx_hash}'에 대한 조회 결과를 찾을 수 없습니다.\n\n지원되는 모든 체인에서 조회했지만 결과를 찾지 못했습니다.\n\n트랜잭션 해시 형식을 확인해주세요. (예: 64자 hex 문자열 또는 Base64 형식)")]}
    except Exception as e:
        logger.error(f"트랜잭션 조회 실패: {e}", exc_info=True)
        return {"messages": [AIMessage(content=f"트랜잭션 조회 중 오류가 발생했습니다: {str(e)}\n\n지원되는 체인: Bitcoin, Ethereum, BNB Smart Chain, Polygon, Tron, Arbitrum, Optimism, Solana, TON 등 31개 체인")]}

