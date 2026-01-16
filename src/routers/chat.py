"""
Chat 라우터 (Refactored)
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from chatbot import mongodb_client, get_chatbot_graph
from chatbot.models import get_default_chat_state
from langchain_core.messages import HumanMessage, AIMessage
import logging
import json
import uuid
import re

# 로거 설정
logger = logging.getLogger(__name__)

# 라우터 설정
router = APIRouter(prefix="", tags=["chat"])

# 템플릿은 register_chat_routes에서 주입받음
_templates = None

# --- 상수 및 헬퍼 함수 정의 ---

NODE_DISPLAY_NAMES = {
    "router": "🔀 라우팅 중...",
    "simple_chat_specialist": "💬 응답 생성 중...",
    "faq_specialist": "📚 FAQ 검색 중...",
    "transaction_specialist": "🔍 트랜잭션 조회 중...",
    "planner": "📋 검색 계획 중...",
    "researcher": "🔎 웹 검색 중...",
    "grader": "📊 결과 평가 중...",
    "writer": "✍️ 응답 작성 중...",
    "intent_clarifier": "🤔 의도 확인 중...",
    "save_response": "💾 저장 중...",
    "coordinator": "🤖 조정자 실행 중..."
}
# 허용할 노드 명시 (Whitelist)
# 이 노드들의 출력만 사용자에게 스트리밍됩니다.
ALLOWED_STREAM_NODES = {
    "writer", 
    "simple_chat_specialist", 
    "faq_specialist", 
    "transaction_specialist", 
    "intent_clarifier"
}

RESPONSE_NODES = {
    "writer", "simple_chat_specialist", "faq_specialist", 
    "intent_clarifier", "transaction_specialist"
}

JSON_KEYWORDS = [
    '"search_queries"', '"research_plan"', '"priority"',
    '"score"', '"is_sufficient"', '"feedback"', '"missing_information"'
]

def clean_hidden_json(content: str) -> str:
    """
    LLM 응답 앞부분에 포함된 JSON 메타데이터(검색 쿼리 등)를 제거합니다.
    """
    cleaned_content = content.strip()
    
    # JSON 구조가 시작되고 특정 키워드가 포함된 경우
    if cleaned_content.startswith('{') and any(k in cleaned_content[:500] for k in JSON_KEYWORDS):
        brace_count = 0
        end_idx = 0
        for i, char in enumerate(cleaned_content):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if end_idx > 0:
            # JSON 부분 제거 및 앞쪽 공백/개행 제거
            return re.sub(r'^\s*\n\s*\n\s*', '', cleaned_content[end_idx:].lstrip()).strip()
            
    return cleaned_content

# extract_search_info_from_node_output 함수는 src.services.chat_service에서 import 가능
# 필요시 아래 주석을 해제하여 사용:
# from src.services.chat_service import extract_search_info_from_node_output

# --- 라우트 정의 ---

def register_chat_routes(app, templates: Jinja2Templates):
    """Chat 라우트를 FastAPI 앱에 등록"""
    global _templates
    _templates = templates
    app.include_router(router)

@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """챗봇 페이지"""
    if _templates is None:
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="templates")
    else:
        templates = _templates
    return templates.TemplateResponse("pages/chatbot.html", {"request": request})

@router.post("/api/chat/stream")
async def chat_stream(request: Request):
    """
    스트리밍 채팅 엔드포인트 (Server-Sent Events)
    LangGraph 1.0 astream_events 사용
    """
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        session_id = data.get("session_id", str(uuid.uuid4()))

        if not message:
            async def error_stream():
                yield f"data: {json.dumps({'type': 'error', 'content': '메시지를 입력해주세요.'})}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")

        logger.info(f"[STREAM] 스트리밍 요청 - Session: {session_id}, Message: {message[:50]}...")

        # 1. 그래프 및 히스토리 로드
        graph = get_chatbot_graph()
        history_messages = []
        try:
            history = await mongodb_client.get_conversation_history(session_id, limit=10)
            for msg in history:
                if msg.get("role") == "user":
                    history_messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    history_messages.append(AIMessage(content=msg.get("content", "")))
        except Exception as e:
            logger.warning(f"[STREAM] 대화 기록 조회 실패 (계속 진행): {e}")

        # 2. 초기 상태 설정
        initial_state = get_default_chat_state(
            session_id=session_id,
            messages=history_messages + [HumanMessage(content=message)]
        )

        # 3. 스트리밍 생성기 함수
        async def generate_stream():
            final_response = ""
            current_node = None
            accumulated_content = {}
            coordinator_state_tracker = None
            # 초기 messages 개수 저장 (새로운 메시지만 추출하기 위해)
            initial_messages_count = len(initial_state.get("messages", []))

            try:
                # User 메시지 저장
                await mongodb_client.save_message(session_id, "user", message)
                yield f"data: {json.dumps({'type': 'start', 'session_id': session_id})}\n\n"

                # LangGraph 이벤트 루프
                # coordinator 내부의 에이전트 실행은 LangGraph 노드가 아니므로
                # on_chain_end에서 coordinator의 output을 확인하여 실행된 노드들을 추론해야 함
                async for event in graph.astream_events(initial_state, version="v2"):
                    event_type = event.get("event", "")
                    event_name = event.get("name", "")
                    
                    # 모든 이벤트 로깅 (디버깅용 - 처음 50개만)
                    if event_type in ["on_chain_start", "on_chain_end"]:
                        logger.debug(f"🔍 [EVENT] {event_type}: {event_name}")

                    # --- [이벤트 1] 노드 시작 (상태 업데이트) ---
                    if event_type == "on_chain_start":
                        parts = event_name.split("/")
                        
                        # 노드 이름 추출: 경로에서 NODE_DISPLAY_NAMES에 있는 실제 노드 이름 찾기
                        actual_node_name = None
                        
                        # 1단계: 모든 부분을 확인해서 NODE_DISPLAY_NAMES에 있는 노드 찾기
                        for part in parts:
                            if part in NODE_DISPLAY_NAMES:
                                actual_node_name = part
                                break
                        
                        # 2단계: 없으면 마지막 부분 사용
                        if not actual_node_name:
                            actual_node_name = parts[-1] if parts else event_name
                        
                        # 내부 LangChain 컴포넌트 제외 (LangGraph, RunnableSequence 등)
                        skip_nodes = ["LangGraph", "RunnableSequence", "ChatPromptTemplate", "ChatOpenAI", "StrOutputParser"]
                        
                        # [디버깅용 로그] 실제 실행되는 노드 이름을 확인하세요!
                        if actual_node_name not in skip_nodes:
                            logger.info(f"👉 [NODE START] node_name: {actual_node_name} (path: {event_name})")
                            logger.info(f"   - NODE_DISPLAY_NAMES에 있음: {actual_node_name in NODE_DISPLAY_NAMES}")
                            if actual_node_name in NODE_DISPLAY_NAMES:
                                logger.info(f"   - 표시 이름: {NODE_DISPLAY_NAMES[actual_node_name]}")
                            logger.info(f"   - ALLOWED_STREAM_NODES에 있음: {actual_node_name in ALLOWED_STREAM_NODES}")

                        # UI 상태 업데이트: NODE_DISPLAY_NAMES에 있는 노드만 표시
                        if actual_node_name in NODE_DISPLAY_NAMES and actual_node_name not in skip_nodes:
                            display_name = NODE_DISPLAY_NAMES[actual_node_name]
                            logger.info(f"📢 [UI UPDATE] 노드 시작 표시: {actual_node_name} - {display_name}")
                            yield f"data: {json.dumps({'type': 'node', 'node': actual_node_name, 'display': display_name})}\n\n"
                            
                            # Coordinator가 시작되면 내부에서 실행될 노드들 예상 표시
                            # 실제로는 coordinator가 실행을 완료한 후 on_chain_end에서 정확한 노드 목록을 확인할 수 있지만,
                            # 사용자 경험을 위해 coordinator가 시작될 때 router는 미리 표시
                            if actual_node_name == "coordinator":
                                # Coordinator 내부에서 router는 항상 실행됨
                                if "router" in NODE_DISPLAY_NAMES:
                                    logger.info(f"📢 [COORDINATOR] router 노드 미리 표시")
                                    yield f"data: {json.dumps({'type': 'node', 'node': 'router', 'display': NODE_DISPLAY_NAMES['router']}, ensure_ascii=False)}\n\n"
                            
                            # 스트리밍 허용 노드 체크
                            if actual_node_name in ALLOWED_STREAM_NODES:
                                current_node = actual_node_name
                                if actual_node_name not in accumulated_content:
                                    accumulated_content[actual_node_name] = ""

                    # --- [이벤트 2] 토큰 스트리밍 (LLM 출력) ---
                    elif event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            token = chunk.content
                            
                            # event_name에서 실제 노드 이름 추출
                            # 예: "LangGraph/coordinator/writer/LangGraph" -> "writer"
                            stream_node_name = None
                            if "/" in event_name:
                                parts = event_name.split("/")
                                for part in parts:
                                    if part in ALLOWED_STREAM_NODES:
                                        stream_node_name = part
                                        break
                            else:
                                stream_node_name = event_name if event_name in ALLOWED_STREAM_NODES else None
                            
                            # 허용된 노드의 토큰만 전송
                            if stream_node_name and stream_node_name in ALLOWED_STREAM_NODES:
                                current_node = stream_node_name
                                
                                # accumulated_content에 토큰 추가
                                if current_node not in accumulated_content:
                                    accumulated_content[current_node] = ""
                                accumulated_content[current_node] += token
                                
                                # 토큰 전송 (JSON 필터링은 최종 응답에서만 수행)
                                # logger.debug(f"[TOKEN] {stream_node_name}: {token[:50]}...")
                                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                    # --- [이벤트 3] Coordinator 상태 변경 (기존 유지) ---
                    elif event_type == "on_chain_stream":
                        chunk = event.get("data", {}).get("chunk", {})
                        if isinstance(chunk, dict) and ("coordinator" in event_name.lower()):
                            current_step = chunk.get("current_step")
                            display = chunk.get("current_step_display")
                            if current_step and display and coordinator_state_tracker != current_step:
                                coordinator_state_tracker = current_step
                                yield f"data: {json.dumps({'type': 'node', 'node': current_step, 'display': display})}\n\n"

                    # --- [이벤트 4] 노드 종료 (기존 유지) ---
                    elif event_type == "on_chain_end":
                        # 내부 LangChain 컴포넌트 제외 (공통)
                        skip_nodes = ["LangGraph", "RunnableSequence", "ChatPromptTemplate", "ChatOpenAI", "StrOutputParser"]
                        
                        # event_name에서 실제 노드 이름 추출 (더 정확하게)
                        parts = event_name.split("/")
                        node_name = None
                        
                        # 1단계: NODE_DISPLAY_NAMES에서 찾기 (우선순위 1)
                        for part in parts:
                            if part in NODE_DISPLAY_NAMES and part not in skip_nodes:
                                node_name = part
                                break
                        
                        # 2단계: ALLOWED_STREAM_NODES 또는 RESPONSE_NODES에서 찾기
                        if not node_name:
                            for part in parts:
                                if (part in ALLOWED_STREAM_NODES or part in RESPONSE_NODES) and part not in skip_nodes:
                                    node_name = part
                                    break
                        
                        # 3단계: 그래도 없으면 마지막 부분 사용 (skip_nodes 제외)
                        if not node_name:
                            for part in reversed(parts):
                                if part not in skip_nodes:
                                    node_name = part
                                    break
                            if not node_name:
                                node_name = parts[-1] if parts else event_name
                        
                        output = event.get("data", {}).get("output", {})
                        
                        # 디버깅 로그 (모든 노드 종료 시)
                        # skip_nodes가 아닌 경우에만 로깅
                        if node_name not in skip_nodes:
                            logger.info(f"👉 [NODE END] node_name: {node_name} (path: {event_name}), output_type: {type(output)}")
                            logger.info(f"   - NODE_DISPLAY_NAMES에 있음: {node_name in NODE_DISPLAY_NAMES}")
                            if node_name in NODE_DISPLAY_NAMES:
                                logger.info(f"   - 표시 이름: {NODE_DISPLAY_NAMES[node_name]}")
                        
                        # 출력 구조 확인
                        if isinstance(output, dict):
                            logger.info(f"[CHAIN_END] output keys: {output.keys()}")
                            if "messages" in output:
                                msgs = output.get('messages', [])
                                logger.info(f"[CHAIN_END] messages count: {len(msgs)}")
                                if msgs:
                                    last_msg = msgs[-1]
                                    content_preview = last_msg.content[:100] if hasattr(last_msg, "content") else str(last_msg)[:100]
                                    logger.info(f"[CHAIN_END] last message preview: {content_preview}...")

                        # 노드별 검색 정보 추출 (생각하는 과정용)
                        search_info = {}
                        if isinstance(output, dict):
                            # FAQ 검색 결과 (db_search_results)
                            db_results = output.get("db_search_results", [])
                            if db_results:
                                search_info["db_results"] = []
                                for r in db_results[:5]:  # 최대 5개만
                                    # URL 추출 (여러 필드에서 시도)
                                    url = r.get("url") or r.get("source") or r.get("href") or ""
                                    # 메타데이터에서 URL 추출
                                    metadata = r.get("metadata", {})
                                    if not url and isinstance(metadata, dict):
                                        url = metadata.get("url") or metadata.get("source") or metadata.get("href") or ""
                                    
                                    # 제목 추출
                                    title = r.get("title") or r.get("text", "")[:50] or "FAQ 결과"
                                    
                                    search_info["db_results"].append({
                                        "title": title,
                                        "text": r.get("text", "")[:200],
                                        "url": url,
                                        "score": r.get("score", 0.0)
                                    })
                            
                            # 웹 검색 결과 (web_search_results)
                            web_results = output.get("web_search_results", [])
                            if web_results:
                                search_info["web_results"] = [
                                    {
                                        "title": r.get("title", "제목 없음"),
                                        "snippet": r.get("snippet", "")[:200],
                                        "url": r.get("url", "")
                                    }
                                    for r in web_results[:5]  # 최대 5개만
                                ]
                            
                            # 검색 쿼리 (search_queries)
                            search_queries = output.get("search_queries", [])
                            if search_queries:
                                search_info["queries"] = search_queries[:5]  # 최대 5개만
                            
                            # 트랜잭션 결과 (transaction_results)
                            tx_results = output.get("transaction_results")
                            if tx_results:
                                search_info["transaction_results"] = tx_results
                            
                            # 연구 계획 (research_plan)
                            research_plan = output.get("research_plan", "")
                            if research_plan:
                                search_info["research_plan"] = research_plan[:200]
                            
                            # 검색 정보 전송 (생각하는 과정용)
                            # search_info가 비어있더라도 노드 정보는 전송 (클라이언트에서 기본 표시 가능)
                            logger.info(f"📊 [SEARCH_INFO] {node_name}: 쿼리 {len(search_info.get('queries', []))}개, DB {len(search_info.get('db_results', []))}개, 웹 {len(search_info.get('web_results', []))}개")
                            yield f"data: {json.dumps({'type': 'node_search', 'node': node_name, 'search_info': search_info})}\n\n"

                        # 노드 종료 시 UI 업데이트 (중요한 노드만)
                        # NODE_DISPLAY_NAMES에 있는 노드가 종료되면 상태 업데이트 전송
                        if node_name in NODE_DISPLAY_NAMES and node_name not in skip_nodes:
                            logger.info(f"✅ [NODE END] {node_name} 완료")

                        # Coordinator 전문가 선택 로직 및 내부 에이전트 추적
                        if node_name == "coordinator" and isinstance(output, dict):
                            specialist = output.get("specialist_used", "")
                            question_type = output.get("question_type")
                            
                            # Coordinator 내부에서 실행된 에이전트 추론
                            # specialist_used 또는 question_type을 기반으로 실제 실행된 노드 추론
                            executed_nodes = []
                            
                            # 1. Router가 실행되었을 가능성 (coordinator가 router를 호출)
                            if question_type or specialist:
                                executed_nodes.append("router")
                            
                            # 2. 선택된 Specialist 추론
                            target_node = None
                            if specialist == "faq" or (question_type and str(question_type).endswith("FAQ")):
                                target_node = "faq_specialist"
                                executed_nodes.append("faq_specialist")
                            elif specialist == "web_search" or (question_type and "WEB_SEARCH" in str(question_type)):
                                target_node = "planner"
                                executed_nodes.extend(["planner", "researcher", "grader", "writer"])
                            elif specialist == "transaction" or (question_type and "TRANSACTION" in str(question_type)):
                                target_node = "transaction_specialist"
                                executed_nodes.append("transaction_specialist")
                            elif specialist == "simple_chat" or (question_type and "SIMPLE_CHAT" in str(question_type)):
                                target_node = "simple_chat_specialist"
                                executed_nodes.append("simple_chat_specialist")
                            
                            # 실행된 노드들에 대해 이벤트 전송 (실행 순서대로 표시)
                            # coordinator 내부에서 실행된 노드들이 LangGraph 노드가 아니므로 여기서 전송
                            # router -> specialist 순서로 표시
                            logger.info(f"🔍 [COORDINATOR] 실행된 노드 추론: {executed_nodes}")
                            for exec_node in executed_nodes:
                                if exec_node in NODE_DISPLAY_NAMES:
                                    display_name = NODE_DISPLAY_NAMES[exec_node]
                                    logger.info(f"🔍 [COORDINATOR] 내부 에이전트 감지: {exec_node} - {display_name}")
                                    # 노드가 실행되었다고 가정하고 표시
                                    yield f"data: {json.dumps({'type': 'node', 'node': exec_node, 'display': display_name}, ensure_ascii=False)}\n\n"
                                else:
                                    logger.warning(f"⚠️ [COORDINATOR] {exec_node}가 NODE_DISPLAY_NAMES에 없음 - 표시되지 않음")
                            
                            # 3. Coordinator의 state에서 검색 정보 추출 (내부 에이전트들이 실행된 결과)
                            coordinator_search_info = {}
                            
                            # DB 검색 결과 (FAQAgent가 실행되었을 경우)
                            db_results = output.get("db_search_results", [])
                            if db_results:
                                coordinator_search_info["db_results"] = []
                                for r in db_results[:5]:
                                    url = r.get("url") or r.get("source") or r.get("href") or ""
                                    metadata = r.get("metadata", {})
                                    if not url and isinstance(metadata, dict):
                                        url = metadata.get("url") or metadata.get("source") or metadata.get("href") or ""
                                    title = r.get("title") or r.get("text", "")[:50] or "FAQ 결과"
                                    coordinator_search_info["db_results"].append({
                                        "title": title,
                                        "text": r.get("text", "")[:200],
                                        "url": url,
                                        "score": r.get("score", 0.0)
                                    })
                            
                            # 웹 검색 결과 (PlannerAgent → ResearcherAgent가 실행되었을 경우)
                            web_results = output.get("web_search_results", [])
                            if web_results:
                                coordinator_search_info["web_results"] = [
                                    {
                                        "title": r.get("title", "제목 없음"),
                                        "snippet": r.get("snippet", "")[:200],
                                        "url": r.get("url", "")
                                    }
                                    for r in web_results[:5]
                                ]
                            
                            # 검색 쿼리
                            search_queries = output.get("search_queries", [])
                            if search_queries:
                                coordinator_search_info["queries"] = search_queries[:5]
                            
                            # 연구 계획 (research_plan)
                            research_plan = output.get("research_plan", "")
                            if research_plan:
                                coordinator_search_info["research_plan"] = research_plan[:200] if isinstance(research_plan, str) else str(research_plan)[:200]
                            
                            # Coordinator의 검색 정보 로깅 (디버깅용)
                            logger.info(f"📋 [COORDINATOR] 검색 정보 추출 완료:")
                            logger.info(f"   - 쿼리: {len(coordinator_search_info.get('queries', []))}개")
                            logger.info(f"   - DB 결과: {len(coordinator_search_info.get('db_results', []))}개")
                            logger.info(f"   - 웹 결과: {len(coordinator_search_info.get('web_results', []))}개")
                            logger.info(f"   - 연구 계획: {'있음' if coordinator_search_info.get('research_plan') else '없음'}")
                            logger.info(f"   - 실행된 노드: {executed_nodes}")
                            
                            # Coordinator 내부 에이전트들의 검색 정보 전송
                            # coordinator_search_info에 정보가 있으면 각 노드에 맞게 전송
                            # 검색 정보가 있어도 없어도 모든 노드에 대해 node_search 이벤트 전송 (생각하는 과정 표시용)
                            for exec_node in executed_nodes:
                                if exec_node not in ["router"]:  # router는 검색 정보가 없음
                                    node_search_info = {}
                                    
                                    # coordinator_search_info에 정보가 있으면 노드별로 맞는 정보만 포함
                                    if coordinator_search_info:
                                        if exec_node == "faq_specialist":
                                            # FAQ 관련 정보만
                                            if "db_results" in coordinator_search_info:
                                                node_search_info["db_results"] = coordinator_search_info["db_results"]
                                            if "queries" in coordinator_search_info:
                                                node_search_info["queries"] = coordinator_search_info["queries"]
                                        elif exec_node in ["planner", "researcher"]:
                                            # 웹 검색 관련 정보만
                                            if "web_results" in coordinator_search_info:
                                                node_search_info["web_results"] = coordinator_search_info["web_results"]
                                            if "queries" in coordinator_search_info:
                                                node_search_info["queries"] = coordinator_search_info["queries"]
                                            if "research_plan" in coordinator_search_info:
                                                node_search_info["research_plan"] = coordinator_search_info["research_plan"]
                                        elif exec_node == "grader":
                                            # Grader는 평가 정보만
                                            if "queries" in coordinator_search_info:
                                                node_search_info["queries"] = coordinator_search_info["queries"]
                                        elif exec_node == "writer":
                                            # Writer는 모든 검색 정보 포함 (최종 응답 생성용)
                                            node_search_info = coordinator_search_info.copy()
                                    
                                    # node_search 이벤트 전송 (정보가 없어도 단계 표시를 위해 항상 전송)
                                    logger.info(f"📊 [COORDINATOR] {exec_node} 검색 정보 전송: 쿼리 {len(node_search_info.get('queries', []))}개, DB {len(node_search_info.get('db_results', []))}개, 웹 {len(node_search_info.get('web_results', []))}개")
                                    yield f"data: {json.dumps({'type': 'node_search', 'node': exec_node, 'search_info': node_search_info}, ensure_ascii=False)}\n\n"
                            
                            # 4. Coordinator의 output에 messages가 있으면 응답 추출
                            # 주의: coordinator의 output에는 이전 대화의 모든 messages가 포함될 수 있음
                            # 실제 응답은 각 전문가 노드(simple_chat_specialist 등)에서 생성되므로,
                            # coordinator의 messages는 건너뛰고 실제 응답 노드의 output을 사용
                            logger.info("[CHAIN_END] coordinator - 실제 응답은 전문가 노드에서 처리하므로 건너뜀")

                        # 모든 노드의 output에서 messages 확인 (응답 누락 방지)
                        # 특히 ainvoke를 사용하는 노드들은 스트리밍되지 않으므로 on_chain_end에서 처리해야 함
                        # coordinator는 이미 위에서 처리했으므로 건너뜀 (중복 방지)
                        if node_name != "coordinator" and isinstance(output, dict) and "messages" in output:
                            msgs = output.get("messages", [])
                            if msgs:
                                # 새로운 메시지만 추출 (이전 대화 메시지 제외)
                                # initial_messages_count 이후의 메시지만 확인
                                new_messages = msgs[initial_messages_count:] if len(msgs) > initial_messages_count else msgs[-1:] if msgs else []
                                
                                if not new_messages:
                                    # 새로운 메시지가 없으면 마지막 메시지 사용 (fallback)
                                    logger.warning(f"[CHAIN_END] {node_name} - 새로운 메시지 없음, 마지막 메시지 사용")
                                    new_messages = [msgs[-1]]
                                
                                # 마지막 새 메시지만 사용
                                last_msg = new_messages[-1]
                                content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                                logger.info(f"[CHAIN_END] {node_name} - 전체 messages: {len(msgs)}개, 초기: {initial_messages_count}개, 새로운: {len(new_messages)}개")
                                
                                # 응답 노드인 경우 무조건 처리
                                if node_name in ALLOWED_STREAM_NODES or node_name in RESPONSE_NODES:
                                    logger.info(f"[CHAIN_END] {node_name} 처리 시작 (응답 노드)")
                                    logger.info(f"[CHAIN_END] {node_name} - messages: {len(msgs)}개, content 길이: {len(content) if content else 0}")
                                    
                                    if content and content.strip():
                                        existing_content = accumulated_content.get(node_name, "")
                                        logger.info(f"[CHAIN_END] {node_name} - existing_content 길이: {len(existing_content)}")
                                        
                                        # 기존에 전송된 내용과 다른 경우, 또는 아직 전송되지 않은 경우
                                        if not existing_content or existing_content != content:
                                            # JSON 필터링 적용
                                            cleaned_content = clean_hidden_json(content)
                                            logger.info(f"[CHAIN_END] {node_name} - 필터링 후 길이: {len(cleaned_content) if cleaned_content else 0}")
                                            if cleaned_content:
                                                logger.info(f"[RESPONSE] {node_name}: {cleaned_content[:100]}...")
                                                # 통짜 응답을 토큰으로 전송 (한 번에)
                                                yield f"data: {json.dumps({'type': 'token', 'content': cleaned_content})}\n\n"
                                                accumulated_content[node_name] = cleaned_content
                                                logger.info(f"[RESPONSE] {node_name} 전송 완료 - accumulated_content에 추가됨")
                                            else:
                                                logger.warning(f"[RESPONSE] {node_name}: 필터링 후 내용이 비어있음")
                                        else:
                                            logger.debug(f"[RESPONSE] {node_name}: 이미 전송된 내용과 동일, 건너뜀")
                                    else:
                                        logger.warning(f"[RESPONSE] {node_name}: content가 없음")
                                
                                # 응답 노드가 아니더라도, accumulated_content가 비어있고 content가 있으면 저장
                                # (마지막 수단으로 응답 추출)
                                elif not accumulated_content and content and content.strip():
                                    logger.warning(f"[CHAIN_END] {node_name}는 응답 노드가 아니지만 messages 발견 - 응답 누락 방지를 위해 저장")
                                    cleaned_content = clean_hidden_json(content)
                                    if cleaned_content:
                                        logger.info(f"[RESPONSE] {node_name}에서 응답 발견 (폴백): {cleaned_content[:100]}...")
                                        yield f"data: {json.dumps({'type': 'token', 'content': cleaned_content})}\n\n"
                                        accumulated_content[node_name] = cleaned_content
                        else:
                            # output에 messages가 없는 경우
                            if node_name in ALLOWED_STREAM_NODES or node_name in RESPONSE_NODES:
                                logger.warning(f"[CHAIN_END] {node_name} - output에 messages가 없음 (output type: {type(output)})")
                            else:
                                logger.debug(f"[CHAIN_END] {node_name} - ALLOWED_STREAM_NODES에 없음 (현재 허용 노드: {ALLOWED_STREAM_NODES})")

                # [Loop 종료 후] 최종 정리
                # accumulated_content에 아무것도 없으면 on_chain_end에서 응답을 놓친 것일 수 있음
                # 이 경우 최종 그래프 실행 결과에서 messages를 추출해야 함
                if accumulated_content:
                    if "writer" in accumulated_content:
                        raw_final = accumulated_content["writer"]
                    elif "coordinator" in accumulated_content:
                        raw_final = accumulated_content["coordinator"]
                    else:
                        raw_final = list(accumulated_content.values())[-1]
                    
                    # 최종 저장 시에만 JSON 태그 청소
                    final_response = clean_hidden_json(raw_final)
                    logger.info(f"[FINAL] 최종 응답 길이: {len(final_response)}자 (from accumulated_content)")
                else:
                    # accumulated_content가 비어있으면 그래프의 최종 상태에서 직접 추출 시도
                    logger.warning("[FINAL] accumulated_content가 비어있음 - 그래프 최종 상태에서 응답 추출 시도")
                    
                    # 그래프를 다시 실행해서 최종 상태 확인 (비효율적이지만 응답 누락 방지)
                    # 대신 마지막 이벤트의 output에서 messages 확인
                    final_response = ""
                    
                    # 주의: 이 부분은 이미 완료된 이벤트 스트림이므로,
                    # 실제로는 클라이언트 측에서 final_response를 사용해야 함
                    logger.warning("[FINAL] accumulated_content가 비어있음 - 클라이언트에서 final_response 확인 필요")
                
                # 완료 이벤트 전송
                logger.info(f"[DONE] 완료 이벤트 전송 시작 - final_response 길이: {len(final_response)}자")
                logger.info(f"[DONE] accumulated_content: {list(accumulated_content.keys())}")
                done_event = f"data: {json.dumps({'type': 'done', 'final_response': final_response}, ensure_ascii=False)}\n\n"
                logger.info(f"[DONE] done 이벤트 문자열: {done_event[:200]}...")
                yield done_event
                logger.info("[DONE] 완료 이벤트 전송 완료 - yield 실행됨")
                
                # 추가 flush (확실히 전송되도록)
                import sys
                if hasattr(sys.stdout, 'flush'):
                    sys.stdout.flush()

            except Exception as e:
                logger.error(f"[STREAM] 스트리밍 중 오류: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'content': f'오류 발생: {str(e)}'})}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
            }
        )

    except Exception as e:
        logger.error(f"[STREAM] 요청 처리 실패: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """대화 기록 조회"""
    try:
        history = await mongodb_client.get_conversation_history(session_id, limit=50)
        serialized_history = []
        for msg in history:
            serialized_msg = dict(msg)
            # ObjectId 및 datetime 문자열 변환
            if "_id" in serialized_msg:
                serialized_msg["_id"] = str(serialized_msg["_id"])
            if "created_at" in serialized_msg and hasattr(serialized_msg["created_at"], "isoformat"):
                serialized_msg["created_at"] = serialized_msg["created_at"].isoformat()
            serialized_history.append(serialized_msg)
        return JSONResponse(content={"history": serialized_history})
    except Exception as e:
        logger.error(f"대화 기록 조회 실패: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

@router.delete("/api/chat/history/{session_id}")
async def clear_chat_history(session_id: str):
    """대화 기록 삭제"""
    try:
        success = await mongodb_client.clear_conversation(session_id)
        return JSONResponse(content={"success": success})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)