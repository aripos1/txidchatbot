#chain_configs.py

import os
from dotenv import load_dotenv

load_dotenv()

# Solana getTransaction 응답에서 시스템 전송 정보를 추출하는 헬퍼 함수 (람다 내부에 포함시키기 복잡해서 개념적으로 분리)
# 실제로는 이 로직을 람다 내에 next()와 제너레이터 표현식으로 구현합니다.
def find_solana_system_transfer(instructions_list):
    if not instructions_list:
        return None
    for inst in instructions_list:
        if inst.get("programId") == "11111111111111111111111111111111": # System Program ID
            parsed_info = inst.get("parsed", {}).get("info", {})
            if inst.get("parsed", {}).get("type") == "transfer":
                return {
                    "source": parsed_info.get("source"),
                    "destination": parsed_info.get("destination"),
                    "lamports": int(parsed_info.get("lamports", 0)) # lamports는 정수여야 함
                }
    return None

def normalize_solana_transaction(res: dict):
    """Solana 트랜잭션 응답을 정규화하는 함수"""
    if not isinstance(res.get("result"), dict) or not res.get("result", {}).get("transaction"):
        return None

    txid = res.get("result", {}).get("transaction", {}).get("signatures", [None])[0]
    if not txid:
        return None

    # 기본값 설정
    from_address = None
    to_address = None
    value = None

    # accountKeys에서 from 주소 추출 (첫 번째 계정이 보통 발신자)
    account_keys = res.get("result", {}).get("transaction", {}).get("message", {}).get("accountKeys", [])
    if account_keys:
        from_address = account_keys[0].get("pubkey")

    # 단순 SOL 전송 (System Program) 찾기
    system_transfer_info = None
    
    # instructions와 innerInstructions 모두에서 System Program의 transfer를 찾음
    all_instruction_groups = [res.get("result", {}).get("transaction", {}).get("message", {}).get("instructions", [])] + \
                             [inner_inst_set.get("instructions", []) for inner_inst_set in res.get("result", {}).get("meta", {}).get("innerInstructions", [])]

    for instruction_group in all_instruction_groups:
        for inst in instruction_group:
            if inst.get("programId") == "11111111111111111111111111111111": # System Program ID
                parsed_info = inst.get("parsed", {}).get("info", {})
                if inst.get("parsed", {}).get("type") == "transfer":
                    system_transfer_info = {
                        "source": parsed_info.get("source"),
                        "destination": parsed_info.get("destination"),
                        "lamports": int(parsed_info.get("lamports", 0))
                    }
                    break # 첫 번째 시스템 전송만 사용
        if system_transfer_info:
            break

    if system_transfer_info:
        to_address = system_transfer_info["destination"]
        value = system_transfer_info["lamports"] / 1e9 # lamports to SOL

    return {
        "txid": txid,
        "from": from_address,
        "to": to_address,
        "value": value,
        "blockNumber": res.get("result", {}).get("slot"),
        "status": "confirmed" if res.get("result") and res.get("result", {}).get("meta", {}).get("err") is None else "failed",
        "chain": "solana",
        "explorer": "https://solscan.io/tx/",
        "symbol": "SOL"
    }

def get_chain_configs():
    return {
        "bitcoin": {
            "name": "Bitcoin",
            "symbol": "BTC",
            "explorer": "https://www.blockchain.com/btc/tx/",
            "api": lambda txid: f"https://api.blockcypher.com/v1/btc/main/txs/{txid}",
            "normalize": lambda res: {
                "txid": res.get("hash"),
                "from": res.get("inputs", [{}])[0].get("addresses", [None])[0],
                "to": res.get("outputs", [{}])[0].get("addresses", [None])[0],
                "value": res.get("total", 0) / 1e8,
                "blockNumber": res.get("block_height"),
                "status": "confirmed" if res.get("confirmations", 0) > 0 else "pending",
                "chain": "bitcoin",
                "explorer": "https://www.blockchain.com/btc/tx/",
                "symbol": "BTC"
            } if res.get("hash") and res.get("inputs") and res.get("outputs") else None
        },
        "litecoin": {
            "name": "Litecoin",
            "symbol": "LTC",
            "explorer": "https://live.blockcypher.com/ltc/tx/",
            "api": lambda txid: f"https://api.blockcypher.com/v1/ltc/main/txs/{txid}",
            "normalize": lambda res: {
                "txid": res.get("hash"),
                "from": res.get("inputs", [{}])[0].get("addresses", [None])[0],
                "to": res.get("outputs", [{}])[0].get("addresses", [None])[0],
                "value": res.get("total", 0) / 1e8,
                "blockNumber": res.get("block_height"),
                "status": "confirmed" if res.get("confirmations", 0) > 0 else "pending",
                "chain": "litecoin",
                "explorer": "https://live.blockcypher.com/ltc/tx/",
                "symbol": "LTC"
            } if res.get("hash") and res.get("inputs") and res.get("outputs") else None
        },
        "dogecoin": {
            "name": "Dogecoin",
            "symbol": "DOGE",
            "explorer": "https://live.blockcypher.com/doge/tx/",
            "api": lambda txid: f"https://api.blockcypher.com/v1/doge/main/txs/{txid}",
            "normalize": lambda res: {
                "txid": res.get("hash"),
                "from": res.get("inputs", [{}])[0].get("addresses", [None])[0],
                "to": res.get("outputs", [{}])[0].get("addresses", [None])[0],
                "value": res.get("total", 0) / 1e8,
                "blockNumber": res.get("block_height"),
                "status": "confirmed" if res.get("confirmations", 0) > 0 else "pending",
                "chain": "dogecoin",
                "explorer": "https://live.blockcypher.com/doge/tx/",
                "symbol": "DOGE"
            } if res.get("hash") and res.get("inputs") and res.get("outputs") else None
        },
        "ethereum": {
            "name": "Ethereum",
            "symbol": "ETH",
            "rpc_mode": True,
            "rpc_method": "eth_getTransactionByHash",
            "explorer": "https://etherscan.io/tx/",
            # 이더스캔 V1 API가 2025년 8월 15일 중단되어 RPC 모드로 전환
            # 공개 RPC 엔드포인트 사용 (또는 환경 변수로 커스텀 RPC URL 설정 가능)
            "api": lambda txid: os.getenv('ETHEREUM_RPC_URL', 'https://eth.llamarpc.com'),
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),  # 전체 해시 보존
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "ethereum",
                "explorer": "https://etherscan.io/tx/",
                "symbol": "ETH"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "bnb_smart_chain": {
            "name": "BNB Smart Chain",
            "symbol": "BNB",
            "explorer": "https://bscscan.com/tx/",
            "api": lambda txid: f"https://api.bscscan.com/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}&apikey={os.getenv('BNB_SMART_CHAIN_API_KEY')}",
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "bnb_smart_chain",
                "explorer": "https://bscscan.com/tx/",
                "symbol": "BNB"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "polygon": {
            "name": "Polygon",
            "symbol": "MATIC",
            "rpc_mode": True,
            "rpc_method": "eth_getTransactionByHash",
            "explorer": "https://polygonscan.com/tx/",
            # PolygonScan V1 API가 deprecated되어 RPC 모드로 전환
            # 공개 RPC 엔드포인트 사용 (또는 환경 변수로 커스텀 RPC URL 설정 가능)
            # 공식 RPC: https://polygon-rpc.com 또는 https://rpc-mainnet.maticvigil.com
            "api": lambda txid: os.getenv('POLYGON_RPC_URL', 'https://polygon-rpc.com'),
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "polygon",
                "explorer": "https://polygonscan.com/tx/",
                "symbol": "MATIC"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "tron": {
            "name": "Tron",
            "symbol": "TRX",
            "explorer": "https://tronscan.org/#/transaction/",
            "api": lambda txid: f"https://apilist.tronscan.org/api/transaction-info?hash={txid}",
            "normalize": lambda res: {
                "txid": res.get("hash"),
                "from": res.get("contractData", {}).get("owner_address"),
                "to": res.get("contractData", {}).get("to_address"),
                "value": res.get("contractData", {}).get("amount", 0) / 1e6,
                "blockNumber": res.get("block"),
                "status": "confirmed" if res.get("confirmed") and str(res.get("contractRet")).upper() == "SUCCESS" else ("pending" if not res.get("confirmed") else str(res.get("contractRet", "failed")).lower()),
                "chain": "tron",
                "explorer": "https://tronscan.org/#/transaction/",
                "symbol": "TRX"
            } if res.get("hash") else None
        },
        "arbitrum_one": {
            "name": "Arbitrum One",
            "symbol": "ARB",
            "explorer": "https://arbiscan.io/tx/",
            "api": lambda txid: f"https://api.arbiscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}&apikey={os.getenv('ARBITRUM_API_KEY')}",
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "arbitrum_one",
                "explorer": "https://arbiscan.io/tx/",
                "symbol": "ARB"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "optimism": {
            "name": "Optimism",
            "symbol": "OP",
            "explorer": "https://optimistic.etherscan.io/tx/",
            "api": lambda txid: f"https://api-optimistic.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}&apikey={os.getenv('OPTIMISM_API_KEY')}",
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "optimism",
                "explorer": "https://optimistic.etherscan.io/tx/",
                "symbol": "OP"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "etc": {
            "name": "Ethereum Classic",
            "symbol": "ETC",
            "rpc_mode": True,
            "rpc_method": "eth_getTransactionByHash", # 명시
            "explorer": "https://etc.blockscout.com/tx/",
            "api": lambda txid: "https://etc.blockscout.com/api/eth-rpc", # txid 인자 사용 안 함
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "etc",
                "explorer": "https://etc.blockscout.com/tx/",
                "raw": res, # 필요시 원본 데이터 포함
                "symbol": "ETC"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "avalanche_c_chain": {
            "name": "Avalanche C-Chain",
            "symbol": "AVAX",
            "explorer": "https://snowtrace.io/tx/",
            "api": lambda txid: f"https://api.snowtrace.io/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}&apikey={os.getenv('AVALANCHE_API_KEY')}",
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None, # AVAX
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "avalanche_c_chain",
                "explorer": "https://snowtrace.io/tx/",
                "symbol": "AVAX"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "solana": {
            "name": "Solana ",
            "symbol": "SOL",
            "explorer": "https://solscan.io/tx/",
            "rpc_mode": True,
            "rpc_method": "getTransaction",
            # Helius 무료 API 키를 발급받아 YOUR_HELIUS_API_KEY 부분에 넣거나, 환경 변수에서 로드하세요.
            # 예: "https://mainnet.helius-rpc.com/?api-key=" + os.getenv('HELIUS_API_KEY', '')
            # 키 없이 사용하려면 "https://api.mainnet-beta.solana.com" 사용 (더 엄격한 사용량 제한)
            "api": lambda txid: os.getenv('SOLANA_RPC_URL', "https://api.mainnet-beta.solana.com"), # txid 인자 사용 안 함
            "rpc_params_lambda": lambda txid: [txid, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
            "normalize": lambda res: normalize_solana_transaction(res)
        },
        "ton": {
            "name": "TON",
            "symbol": "TON",
            "explorer": "https://tonviewer.com/transaction/", # Tonviewer uses Base64URL for display in URL
            "api_requires_header_auth": True,
            "api_auth_header_name": "Authorization",
            "api_auth_value_prefix": "Bearer ",
            "api_key_env_var": "TONAPI_KEY",
            # This API expects the HEX encoded transaction hash
            "api": lambda txid_hex: f"https://tonapi.io/v2/blockchain/transactions/{txid_hex}",
            "normalize": lambda res: {
                "txid": res.get("hash"), # tonapi.io returns the hash in hex
                "from": (res.get("in_msg", {}).get("source", {}).get("address")
                         if res.get("in_msg") and res.get("in_msg").get("source")
                         else res.get("account", {}).get("address")),
                "to": (res.get("in_msg", {}).get("destination", {}).get("address")
                       if res.get("in_msg") and res.get("in_msg").get("destination")
                       else (res.get("out_msgs", [{}])[0].get("destination", {}).get("address")
                             if res.get("out_msgs") and len(res.get("out_msgs", [])) > 0 and res.get("out_msgs", [{}])[0].get("destination") else None)),
                "value": (int(res.get("in_msg", {}).get("value", 0)) / 1e9 # TON (nanotons to TON)
                          if res.get("in_msg") and res.get("in_msg").get("value")
                          else None),
                "blockNumber": res.get("mc_block_seqno"),
                "status": "confirmed" if res.get("success") is True else ("failed" if res.get("success") is False else "unknown"),
                "chain": "ton",
                "explorer": "https://tonviewer.com/transaction/", # For display, still links to Tonviewer with Base64URL
                "note": "TON 트랜잭션은 Base64 URL 해시를 사용합니다. 입력값은 Base64 또는 HEX가 될 수 있습니다.",
                "destination_tag": None # TON은 destination tag를 직접 제공하지 않음
            } if res.get("hash") else None,
            "api_url_type": "hex_from_base64_input" # 입력된 txid를 Base64로 간주하고 HEX로 변환
        },
        "mantle": {
            "name": "Mantle",
            "symbol": "MNT",
            "explorer": "https://mantlescan.xyz/tx/",
            "api": lambda txid: f"https://api.mantlescan.xyz/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}&apikey={os.getenv('MANTLE_API_KEY')}",
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "mantle",
                "explorer": "https://mantlescan.xyz/tx/",
                "symbol": "MNT"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "base": {
            "name": "Base",
            "symbol": "BASE",
            "explorer": "https://basescan.org/tx/",
            "api": lambda txid: f"https://api.basescan.org/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}&apikey={os.getenv('BASE_API_KEY')}",
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "base",
                "explorer": "https://basescan.org/tx/",
                "symbol": "BASE"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "wemix": {
            "name": "WEMIX",
            "symbol": "WEMIX",
            "explorer": "https://wemixscan.com/tx/",
            "api": lambda txid: f"https://api.wemixscan.com/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}&apikey={os.getenv('WEMIX_API_KEY')}",
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "wemix",
                "explorer": "https://wemixscan.com/tx/",
                "symbol": "WEMIX"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "endurance": {
            "name": "Endurance", # Fusionist / ACE
            "symbol": "ACE",  # Endurance의 네이티브 토큰 심볼
            # explorer URL도 하이픈(-)을 사용하는 새 주소로 변경
            "explorer": "https://explorer-endurance.fusionist.io/tx/",
            # api URL도 하이픈(-)을 사용하는 새 주소로 변경
            "api": lambda txid: f"https://explorer-endurance.fusionist.io/api?module=transaction&action=gettxinfo&txhash={txid}&apikey={os.getenv('ENDURANCE_API_KEY')}",
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None, # ACE (18 decimals 가정)
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "endurance",
                # explorer URL도 하이픈(-)을 사용하는 새 주소로 변경 (normalize 함수 내에서도 일관성 유지)
                "explorer": "https://explorer-endurance.fusionist.io/tx/",
                "symbol": "ACE"  # normalize 함수에도 symbol 추가
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "blast": {
            "name": "Blast",
            "symbol": "BLAST",
            "rpc_mode": True,
            "rpc_method": "eth_getTransactionByHash",
            "explorer": "https://blastscan.io/tx/",
            # BlastScan V1 API가 deprecated되어 RPC 모드로 전환
            # 공개 RPC 엔드포인트 사용 (또는 환경 변수로 커스텀 RPC URL 설정 가능)
            "api": lambda txid: os.getenv('BLAST_RPC_URL', 'https://rpc.ankr.com/blast'),
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "blast",
                "explorer": "https://blastscan.io/tx/",
                "symbol": "BLAST"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "scroll": {
            "name": "Scroll",
            "symbol": "SCR",
            "explorer": "https://scrollscan.com/tx/",
            "api": lambda txid: f"https://api.scrollscan.com/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}&apikey={os.getenv('SCROLL_API_KEY')}",
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "scroll",
                "explorer": "https://scrollscan.com/tx/",
                "symbol": "SCR"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "linea": {
            "name": "Linea",
            "symbol": "ETH_Linea",
            "explorer": "https://lineascan.build/tx/",
            "api": lambda txid: f"https://api.lineascan.build/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}&apikey={os.getenv('LINEA_API_KEY')}",
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "linea",
                "explorer": "https://lineascan.build/tx/",
                "symbol": "ETH_Linea"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "zksync_era": {
            "name": "zkSync Era",
            "symbol": "ETH_zkSync",
            "explorer": "https://explorer.zksync.io/tx/",
            # zkSync Era 공식 블록 탐색기 API 사용
            "api": lambda txid: f"https://block-explorer-api.mainnet.zksync.io/transactions/{txid}", # API 키 필요 여부 문서에서 확인 필요
            "normalize": lambda res: {
                # zkSync Era API 응답 구조에 맞춰 필드 추출
                "txid": res.get("hash"),
                "from": res.get("from"),
                "to": res.get("to"),
                # 'value' 필드는 API 응답에 직접 있는지, 있다면 단위 확인 필요 (ETH, 1e18 가정)
                # 문서상 'value' 필드가 명확하지 않으나, 일반적인 트랜잭션 객체라면 존재할 수 있음
                "value": int(res.get("value", "0"), 10) / 1e18 if res.get("value") is not None else None, # 응답이 10진수 문자열일 수 있음, 확인 필요
                "blockNumber": res.get("blockNumber"), # API가 10진수 정수로 반환하는지 확인
                # 'status' 필드는 API 응답의 'status' 또는 'isL1Originated' 등을 조합하여 결정
                "status": "confirmed" if res.get("status") == "verified" or res.get("status") == "included" else ( # 'verified' 또는 'included' 상태를 confirmed로 간주
                           "pending" if res.get("status") == "pending" else res.get("status", "unknown")
                ),
                "chain": "zksync_era",
                "explorer": "https://explorer.zksync.io/tx/",
                "symbol": "ETH_zkSync"
            } if res.get("hash") else None # 기본적인 응답 유효성 검사 (hash 필드 존재 여부)
        },
        "world_chain": {
            "name": "World Chain",
            "symbol": "WLD",
            "explorer": "https://worldscan.org/tx/",
            # API 기본 URL을 api.worldscan.org로 변경하고, API 키 사용
            "api": lambda txid: f"https://api.worldscan.org/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}&apikey={os.getenv('WORLDCHAIN_API_KEY')}",
            "normalize": lambda res: {
                # 표준 EVM 트랜잭션 상세 정보 정규화 로직
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None, # ETH (18 decimals)
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "world_chain",
                "explorer": "https://worldscan.org/tx/",
                "symbol": "WLD"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "swell_l2": {
            "name": "Swell L2 (Swellchain)",
            "symbol": "SWELL",
            "explorer": "https://explorer.swellnetwork.io/tx/", # 공식 탐색기 주소로 추정/변경
            "rpc_mode": True,
            "rpc_method": "eth_getTransactionByHash",
            # Ankr에서 제공하는 Swell L2 (Swellchain) 공개 RPC 엔드포인트 사용
            "api": lambda txid: "https://rpc.ankr.com/swell", # txid 인자 사용 안 함
            # "rpc_params_lambda"는 기본 EVM [txid]를 사용하므로 별도 정의 불필요
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None, # ETH (Swell L2의 네이티브 토큰)
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "swell_l2",
                "explorer": "https://explorer.swellnetwork.io/tx/", # 정규화된 결과 내 탐색기 URL도 수정
                "symbol": "SWELL"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "kaia": {
            "name": "KAIA",
            "symbol": "KAIA",
            "explorer": "https://kaiascan.io/tx/",
            "rpc_mode": False,
            "api_requires_header_auth": True,
            "api_auth_header_name": "Authorization",
            "api_auth_value_prefix": "Bearer ",
            "api_key_env_var": "KAIA_BEARER_TOKEN",
            "api": lambda txid: f"https://mainnet-oapi.kaiascan.io/api/v1/transactions/{txid}",
            "normalize": lambda res: {
                "txid": res.get("transaction_hash"),
                "from": res.get("from"),
                "to": res.get("to"),
                "value": int(str(res.get("amount", "0"))) / 1e18 if res.get("amount") is not None else None,
                "blockNumber": res.get("block_id"),
                "status": "confirmed" if res.get("status", {}).get("status") == "Success" else (
                           "failed" if res.get("status", {}).get("status") == "Fail" else "pending"
                ),
                "chain": "kaia",
                "explorer": "https://kaiascan.io/tx/",
                "symbol": "KAIA"
            } if res and res.get("transaction_hash") else None
        },
        "xrp": {
            "name": "Ripple",
            "symbol": "XRP",
            "explorer": "https://xrpscan.com/tx/",
            "api_requires_header_auth": False, # XRPSCAN의 이 엔드포인트는 키 없이 시도
            "api": lambda txid: f"https://api.xrpscan.com/api/v1/tx/{txid}",
            "normalize": lambda res: {
                "txid": res.get("hash"),
                "from": res.get("Account"),
                "to": res.get("Destination"), # Payment 트랜잭션에 주로 존재
                "value": (
                    int(amount_val) / 1e6 # drops to XRP
                    if (amount_val := res.get("Amount")) and isinstance(amount_val, str)
                    # IOU (객체 형태 Amount) 처리: 여기서는 단순 value 추출, 실제 사용시 currency, issuer도 고려 필요
                    else (float(amount_obj.get("value", "0")) if (amount_obj := res.get("Amount")) and isinstance(amount_obj, dict) else None)
                ),
                "blockNumber": res.get("ledger_index"),
                "status": "confirmed" if res.get("meta", {}).get("TransactionResult") == "tesSUCCESS" else res.get("meta", {}).get("TransactionResult", "failed_or_pending"),
                "chain": "xrp",
                "explorer": "https://xrpscan.com/tx/",
                "destination_tag": res.get("DestinationTag"), # DestinationTag 필드 추가
                "memo": (
                    # Memos 배열을 가져와서 첫 번째 메모의 MemoData를 디코딩합니다.
                    # 복잡한 조건과 처리를 람다 내에 표현하기 위해 내부 람다(또는 복합 표현식) 사용.
                    # Python 3.8+ 에서 할당 표현식 (:=) 사용 가능.
                    lambda memos_list: (
                        bytes.fromhex(memo_data_hex).decode('utf-8', errors='replace')
                        if (memo_data_hex := (
                            # memos_list가 존재하고, 비어있지 않고, 첫번째 요소가 dict이고,
                            # 그 안에 "Memo" 키가 있고, 그 값도 dict이고, "MemoData" 키가 있을 때 해당 값을 가져옴
                            memos_list[0].get("Memo", {}).get("MemoData")
                            if memos_list and isinstance(memos_list, list) and len(memos_list) > 0 and \
                               isinstance(memos_list[0], dict) and isinstance(memos_list[0].get("Memo"), dict)
                            else None
                        )) and isinstance(memo_data_hex, str) # memo_data_hex가 실제 문자열일 때만 디코딩 시도
                        else "-" # 그 외의 모든 경우 (메모 없거나, 형식 안 맞거나 등) "-" 표시
                    )
                )(res.get("Memos")) # res.get("Memos") 결과를 내부 람다에 인자로 전달
            } if res and res.get("hash") else None # API 응답이 유효하고 해시가 있을 때만 정규화
        },
        "stellar": {
            "name": "Stellar",
            "symbol": "XLM",
            "explorer": "https://stellarchain.io/tx/",
            "api": lambda txid: f"https://horizon.stellar.org/transactions/{txid}",
            "normalize": lambda res: {
                "txid": res.get("hash"),
                "from": res.get("source_account"),
                "to": next((op.get("to") for op in res.get("_embedded", {}).get("operations", {}).get("records", []) if op.get("type") == "payment"), None),
                "value": next((float(op.get("amount", "0")) for op in res.get("_embedded", {}).get("operations", {}).get("records", []) if op.get("type") == "payment" and op.get("asset_type") == "native"), None),
                "blockNumber": res.get("ledger"),
                "status": "confirmed" if res.get("successful") else "failed",
                "chain": "stellar",
                "explorer": "https://stellarchain.io/tx/",
                "symbol": "XLM"
            } if res.get("hash") else None
        },
        "injective": {
            "name": "Injective",
            "symbol": "INJ",
            "explorer": "https://explorer.injective.network/transaction/",
            "api": lambda txid: f"https://lcd.injective.network/cosmos/tx/v1beta1/txs/{txid}",
            "normalize": lambda res: {
                "txid": res.get("tx_response", {}).get("txhash"),
                "from": res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("from_address"),
                "to": res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("to_address"),
                "value": int(res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("amount", [{}])[0].get("amount", "0")) / 1e18 if res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("amount") else None,
                "blockNumber": int(res.get("tx_response", {}).get("height", "0")) if res.get("tx_response", {}).get("height") else None,
                "status": "confirmed" if res.get("tx_response", {}).get("code") == 0 else "failed",
                "chain": "injective",
                "explorer": "https://explorer.injective.network/transaction/",
                "symbol": "INJ"
            } if res.get("tx_response") and res.get("tx_response", {}).get("txhash") else None
        },
        "atom": {
            "name": "Cosmos Hub",
            "symbol": "ATOM",
            "explorer": "https://www.mintscan.io/cosmos/txs/",
            "api": lambda txid: f"https://rest.cosmos.directory/cosmoshub/cosmos/tx/v1beta1/txs/{txid}",
            "normalize": lambda res: {
                "txid": res.get("tx_response", {}).get("txhash"),
                "from": res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("from_address"),
                "to": res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("to_address"),
                "value": int(res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("amount", [{}])[0].get("amount", "0")) / 1e6 if res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("amount") else None,
                "blockNumber": int(res.get("tx_response", {}).get("height", "0")) if res.get("tx_response", {}).get("height") else None,
                "status": "confirmed" if res.get("tx_response", {}).get("code") == 0 else "failed",
                "chain": "atom",
                "explorer": "https://www.mintscan.io/cosmos/txs/",
                "symbol": "ATOM"
            } if res.get("tx_response") and res.get("tx_response", {}).get("txhash") else None
        },
        "xpla": {
            "name": "XPLA",
            "symbol": "XPLA",
            "explorer": "https://explorer.xpla.io/mainnet/tx/",
            "api": lambda txid: f"https://dimension-lcd.xpla.dev/cosmos/tx/v1beta1/txs/{txid}",
            "normalize": lambda res: {
                "txid": res.get("tx_response", {}).get("txhash"),
                "from": res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("from_address"),
                "to": res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("to_address"),
                "value": int(res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("amount", [{}])[0].get("amount", "0")) / 1e18 if res.get("tx", {}).get("body", {}).get("messages", [{}])[0].get("amount") else None,
                "blockNumber": int(res.get("tx_response", {}).get("height", "0")) if res.get("tx_response", {}).get("height") else None,
                "status": "confirmed" if res.get("tx_response", {}).get("code") == 0 else "failed",
                "chain": "xpla",
                "explorer": "https://explorer.xpla.io/mainnet/tx/",
                "symbol": "XPLA"
            } if res.get("tx_response") and res.get("tx_response", {}).get("txhash") else None
        },
        "cronos": {
            "name": "Cronos",
            "symbol": "CRO",
            "explorer": "https://cronoscan.com/tx/",
            "api": lambda txid: f"https://api.cronoscan.com/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}&apikey={os.getenv('CRONOS_API_KEY')}",
            "normalize": lambda res: {
                "txid": res.get("result", {}).get("hash"),
                "from": res.get("result", {}).get("from"),
                "to": res.get("result", {}).get("to"),
                "value": int(res.get("result", {}).get("value", "0x0"), 16) / 1e18 if res.get("result", {}).get("value") is not None else None,
                "blockNumber": int(res.get("result", {}).get("blockNumber", "0x0"), 16) if res.get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res.get("result", {}).get("blockNumber") is not None else "pending",
                "chain": "cronos",
                "explorer": "https://cronoscan.com/tx/",
                "symbol": "CRO"
            } if isinstance(res.get("result"), dict) and res.get("result", {}).get("hash") else None
        },
        "stacks": {
            "name": "Stacks",
            "symbol": "STX",
            "explorer": "https://explorer.stacks.co/txid/",
            "api": lambda txid: f"https://api.hiro.so/extended/v1/tx/{txid if txid.startswith('0x') else '0x'+txid}",
            "normalize": lambda res: {
                "txid": res.get("tx_id"),
                "from": res.get("sender_address"),
                "to": res.get("token_transfer", {}).get("recipient_address") if res.get("tx_type") == "token_transfer" else (res.get("contract_call",{}).get("contract_id") if res.get("tx_type") == "contract_call" else None),
                "value": int(res.get("token_transfer", {}).get("amount", "0")) / 1e6 if res.get("tx_type") == "token_transfer" else None,
                "blockNumber": res.get("block_height"),
                "status": "confirmed" if res.get("tx_status") == "success" else res.get("tx_status", "failed_or_pending"),
                "chain": "stacks",
                "explorer": "https://explorer.stacks.co/txid/"
            } if res.get("tx_id") else None
        },
        "sophon": {
            "name": "Sophon",
            "symbol": "SOPH",
            "explorer": "https://sophscan.xyz/tx/",
            "api_requires_header_auth": False,
            "api_key_env_var": "SOPHSCAN_API_KEY", # 서비스가 API 키를 읽기 위해 필요
            "api_key_is_mandatory": True,
            
            # API 키 없이 순수한 URL 템플릿만 반환
            "api": lambda txid: [
                f"https://api.sophscan.xyz/api?module=transaction&action=gettxreceiptstatus&txhash={txid}",
                f"https://api.sophscan.xyz/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}"
            ],
            
            # 성공적인 응답을 검증하는 최종 normalize 함수
            "normalize": lambda res: {
                "txid": res[1].get("result", {}).get("hash"),
                "from": res[1].get("result", {}).get("from"),
                "to": res[1].get("result", {}).get("to"),
                "value": int(res[1].get("result", {}).get("value", "0x0"), 16) / 1e18 if res[1].get("result", {}).get("value") is not None else 0,
                "blockNumber": int(res[1].get("result", {}).get("blockNumber", "0x0"), 16) if res[1].get("result", {}).get("blockNumber") is not None else None,
                "status": "confirmed" if res[0].get("result", {}).get("status") == "1" else "failed",
                "chain": "sophon",
                "explorer": "https://sophscan.xyz/tx/",
                "symbol": "SOPH"
            } if (
                isinstance(res, list) and len(res) == 2 and
                res[0].get("status") == "1" and res[0].get("message") == "OK" and
                res[1].get("result") is not None and isinstance(res[1].get("result"), dict) and
                res[1].get("result").get("hash") is not None
            ) else None
        },
    }