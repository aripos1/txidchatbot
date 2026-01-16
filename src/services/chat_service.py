"""
Chat 서비스
"""
import logging

logger = logging.getLogger(__name__)


def extract_search_info_from_node_output(node_name: str, output: dict) -> dict:
    """
    노드 출력에서 검색 정보를 추출하여 표준화된 형식으로 반환
    
    Args:
        node_name: 노드 이름
        output: 노드의 출력 딕셔너리
        
    Returns:
        표준화된 검색 정보 딕셔너리 (없으면 빈 딕셔너리)
    """
    if not isinstance(output, dict):
        return {}
    
    # 검색 결과 정보 추출
    db_search_results = output.get("db_search_results", [])
    web_search_results = output.get("web_search_results", [])
    search_queries = output.get("search_queries", [])
    
    # FAQ specialist의 경우: db_search_results에 support_results가 포함될 수 있음
    # support_results는 source가 "bithumb_support"이므로 이를 구분
    if node_name == "faq_specialist" and db_search_results:
        # support_results와 실제 DB 결과 분리
        support_results_list = [r for r in db_search_results if r.get("source") == "bithumb_support"]
        actual_db_results = [r for r in db_search_results if r.get("source") != "bithumb_support"]
        
        # support_results를 web_results로 처리
        if support_results_list:
            web_search_results = support_results_list + web_search_results
        db_search_results = actual_db_results
    
    # 검색 정보가 있으면 표준화된 형식으로 변환
    search_info = {}
    
    if db_search_results:
        search_info["db_results"] = [
            {
                "title": r.get("title") or r.get("text", "")[:100] or "제목 없음",
                "url": r.get("url", ""),
                "score": r.get("score", 0),
                "snippet": r.get("snippet", r.get("text", ""))[:150]
            }
            for r in db_search_results[:3]
        ]
    
    if web_search_results:
        search_info["web_results"] = [
            {
                "title": r.get("title") or r.get("text", "")[:100] or "제목 없음",
                "url": r.get("href") or r.get("url", ""),
                "snippet": r.get("snippet") or r.get("body") or r.get("text", "")[:150]
            }
            for r in web_search_results[:3]
        ]
    
    if search_queries:
        search_info["queries"] = search_queries[:5]
    
    # FAQ specialist 또는 researcher의 경우 검색 쿼리 정보 추가 (사용자 메시지 기반)
    if not search_info.get("queries") and (node_name == "faq_specialist" or node_name == "researcher"):
        # state에서 search_queries를 확인
        # output에 search_queries가 직접 포함되지 않으면 state에서 가져오기 시도
        # 또는 사용자 메시지를 검색 쿼리로 사용
        user_message = ""
        messages = output.get("messages", [])
        if messages:
            for msg in reversed(messages):
                if hasattr(msg, "content") and isinstance(msg.content, str):
                    # HumanMessage 찾기
                    if "HumanMessage" in str(type(msg)) or not hasattr(msg, "role"):
                        user_message = msg.content
                        break
        
        if user_message:
            search_info["queries"] = [user_message[:100]]
    
    return search_info
