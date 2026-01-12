import asyncio
import httpx
import os
import base64
import urllib.parse
import certifi
import logging
from .chain_configs import get_chain_configs
from .cache import cache

CHAIN_CONFIGS = get_chain_configs()

# 로거 설정
logger = logging.getLogger(__name__)

async def detect_transaction(txid: str):
    cached_result = cache.get(txid)
    if cached_result:
        logger.debug(f"Cache hit for txid: {txid}")
        return cached_result
    logger.debug(f"Cache miss for txid: {txid}")

    async with httpx.AsyncClient(verify=certifi.where()) as client:
        tasks = []
        for key, cfg in CHAIN_CONFIGS.items():
            input_txid_for_chain = txid

            if key == "ton" and cfg.get("api_url_type") == "hex_from_base64_input":
                if isinstance(txid, str) and (len(txid) == 44 or len(txid) == 47 or len(txid) == 48) and \
                   ('/' in txid or '+' in txid or txid.endswith('=')):
                    try:
                        logger.debug(f"[{key}] Attempting to convert Base64 TXID '{txid}' to HEX for API call.")
                        missing_padding = len(txid) % 4
                        txid_padded = txid + '=' * (4 - missing_padding) if missing_padding else txid
                        
                        decoded_bytes = None
                        try:
                            decoded_bytes = base64.b64decode(txid_padded)
                        except base64.binascii.Error:
                            txid_urlsafe_corrected = txid_padded.replace('-', '+').replace('_', '/')
                            decoded_bytes = base64.b64decode(txid_urlsafe_corrected)
                        
                        if decoded_bytes:
                            input_txid_for_chain = decoded_bytes.hex()
                            logger.debug(f"[{key}] Converted Base64 TXID '{txid}' to HEX '{input_txid_for_chain}'")
                        else:
                            logger.debug(f"[{key}] Base64 decoding resulted in None for TXID '{txid}'. Using original.")
                    except Exception as e:
                        logger.debug(f"[{key}] Failed to convert TXID '{txid}' from Base64 to HEX: {e}. Using original txid '{txid}'.")
                elif len(txid) == 64 and all(c in '0123456789abcdefABCDEF' for c in txid.lower()):
                    logger.debug(f"[{key}] TXID '{txid}' appears to be already in HEX format.")
                    input_txid_for_chain = txid
                else:
                    logger.debug(f"[{key}] TXID '{txid}' format not recognized as Base64 or HEX for TON. Using original for API call.")
            
            tasks.append(fetch_and_normalize(client, input_txid_for_chain, key, cfg, original_input_txid=txid))

        results_with_errors = await asyncio.gather(*tasks, return_exceptions=True)
        
        found_results = []
        for i, res_or_err in enumerate(results_with_errors):
            chain_key = list(CHAIN_CONFIGS.keys())[i]
            if isinstance(res_or_err, Exception):
                logger.debug(f"[{chain_key}] 작업 중 예외 발생: {res_or_err}")
            elif res_or_err:
                found_results.append(res_or_err)
                
    if found_results:
        logger.debug(f"Setting cache for original input txid: {txid} with results: {found_results}")
        cache.set(txid, found_results)

    return found_results

async def fetch_and_normalize(client: httpx.AsyncClient, txid_for_api: str, key: str, cfg: dict, original_input_txid: str):
    try:
        request_headers = {"User-Agent": "Mozilla/5.0"}
        api_url_or_list = cfg["api"](txid_for_api)
        json_data = None

        if isinstance(api_url_or_list, list):
            logger.debug(f"[{key}] Multi-API call mode activated for {len(api_url_or_list)} URLs.")
            responses_json = []
            
            api_key_value = None
            if not cfg.get("api_requires_header_auth", False) and cfg.get("api_key_env_var"):
                api_key_value = os.getenv(cfg.get("api_key_env_var"))
                if not api_key_value and cfg.get("api_key_is_mandatory", True):
                    logger.warning(f"[{key}] Mandatory API Key not found in env: {cfg.get('api_key_env_var')}")
                    return None

            for base_url in api_url_or_list:
                # 최종 수정: API 키를 URL에 수동으로 추가하여 서버의 파라미터 처리 버그 우회
                final_url = f"{base_url}&apikey={api_key_value}" if api_key_value else base_url
                
                # 최종 수정: 연결 재사용 문제를 해결하기 위해 'Connection: close' 헤더 추가
                multi_call_headers = request_headers.copy()
                multi_call_headers['Connection'] = 'close'
                
                res_multi = await client.get(final_url, headers=multi_call_headers, timeout=30.0)
                logger.debug(f"[{key}] 응답 상태코드 (multi-call): {res_multi.status_code}")
                res_multi.raise_for_status()
                try:
                    responses_json.append(res_multi.json())
                except Exception as e:
                    logger.warning(f"[{key}] JSON 파싱 실패 (URL: {final_url}) → {e}. 응답 본문: {res_multi.text[:200]}")
                    return None
            json_data = responses_json
        
        else: # 단일 URL을 사용하는 경우
            if cfg.get("api_requires_header_auth"):
                api_key_env_var = cfg.get("api_key_env_var")
                auth_header_name = cfg.get("api_auth_header_name")
                auth_value_prefix = cfg.get("api_auth_value_prefix", "")
                if api_key_env_var and auth_header_name:
                    api_key_value = os.getenv(api_key_env_var)
                    if api_key_value:
                        request_headers[auth_header_name] = f"{auth_value_prefix}{api_key_value}"
                    else:
                        logger.debug(f"[{key}] API Key for header auth not found in env: {api_key_env_var}")
                        if cfg.get("api_key_is_mandatory", False): return None
                else:
                    logger.debug(f"[{key}] Header auth configuration missing (api_key_env_var or api_auth_header_name)")

            res = None
            api_url = api_url_or_list # 단일 URL이므로 변수에 다시 할당
            if cfg.get("rpc_mode"):
                request_headers["Content-Type"] = "application/json"
                rpc_method = cfg.get("rpc_method", "eth_getTransactionByHash")
                params_lambda = cfg.get("rpc_params_lambda")
                params = params_lambda(txid_for_api) if params_lambda else [txid_for_api]
                payload = {"jsonrpc": "2.0", "method": rpc_method, "params": params, "id": 1}
                res = await client.post(api_url, json=payload, headers=request_headers, timeout=30.0)
            else:
                res = await client.get(api_url, headers=request_headers, timeout=30.0)

            logger.debug(f"[{key}] 응답 상태코드: {res.status_code}")
            res.raise_for_status()
            try:
                json_data = res.json()
            except Exception as e:
                logger.warning(f"[{key}] JSON 파싱 실패 (상태코드: {res.status_code}) → {e}. 응답 본문: {res.text[:200]}")
                return None

        # 정규화 전, 원본 응답을 로깅하는 통합된 로직
        # RPC 모드인 경우 원본 응답 로깅 (디버깅용)
        if json_data and (key in ["kaia", "ton", "paycoin", "blast", "sophon"] or cfg.get("rpc_mode")):
            # RPC 모드에서 result가 None인 경우만 간단히 로깅
            if cfg.get("rpc_mode") and json_data.get("result") is None:
                logger.debug(f"[{key}] RPC 응답: result가 None (트랜잭션을 찾을 수 없음)")
            elif cfg.get("rpc_mode"):
                result_type = type(json_data.get("result")).__name__
                result_hash = json_data.get("result", {}).get("hash") if isinstance(json_data.get("result"), dict) else None
                logger.debug(f"[{key}] RPC 응답: result 타입={result_type}, hash={result_hash[:20] if result_hash else 'None'}...")
            else:
                logger.debug(f"[{key}] API 원본 응답 (json_data): {json_data}")

        if json_data:
            normalized_data = cfg["normalize"](json_data)
            if normalized_data:
                logger.debug(f"[{key}] 정규화 성공.")
                return normalized_data
            else:
                logger.debug(f"[{key}] 정규화 결과 None (유효하지 않거나 조건 불일치, 또는 응답 구조 확인 필요)")
                return None
        else:
            return None

    except httpx.HTTPStatusError as e:
        # 정상적인 실패(404, 400 등)는 DEBUG 레벨, 실제 오류는 WARNING
        status_code = e.response.status_code
        if status_code in [404, 400]:  # 정상적인 실패
            logger.debug(f"[{key}] HTTP {status_code} (트랜잭션을 찾을 수 없음): {api_url_or_list}")
        else:  # 실제 오류 (500, 401, 403 등)
            logger.warning(f"[{key}] HTTP 오류 (상태코드: {status_code}) → {e}. API: {api_url_or_list}")
            if status_code in [401, 403] and cfg.get("api_requires_header_auth"):
                logger.warning(f"[{key}] API 키가 유효하지 않거나 권한 문제일 수 있습니다.")
        return None
    except httpx.RequestError as e:
        # 네트워크 오류는 WARNING 레벨
        logger.warning(f"[{key}] 요청 오류 → {e}. API: {api_url_or_list}")
        return None
    except Exception as e:
        current_key = key if 'key' in locals() else 'UnknownChain'
        current_api_url = api_url_or_list if 'api_url_or_list' in locals() else 'UnknownAPI'
        logger.error(f"[{current_key}] 알 수 없는 오류 발생 → {e}. API: {current_api_url}", exc_info=True)
        return None