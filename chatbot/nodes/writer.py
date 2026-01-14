"""
Writer 노드 - 답변 종합/작성
"""
import sys
import logging
from datetime import datetime, timezone, timedelta
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from ..models import ChatState
from ..configuration import config
from ..prompts import get_system_prompt_template, get_price_comparison_instruction
from ..utils import ensure_logger_setup, handle_node_error

logger = logging.getLogger(__name__)


def _fix_numbering(text: str) -> str:
    """번호 매기기 검증 및 수정 (1. 1. 1. → 1. 2. 3. 형식으로 수정)"""
    import re
    
    # 번호 패턴 찾기 (1. 2. 3. 형식)
    # 줄 시작 부분의 번호만 매칭
    lines = text.split('\n')
    fixed_lines = []
    current_number = 1
    in_numbered_section = False
    
    for i, line in enumerate(lines):
        # 줄 시작 부분의 번호 패턴 찾기 (1. 또는 1) 형식)
        numbered_match = re.match(r'^(\s*)(\d+)[\.\)]\s+(.+)', line)
        
        if numbered_match:
            indent = numbered_match.group(1)
            number = int(numbered_match.group(2))
            content = numbered_match.group(3)
            
            # 같은 번호가 반복되거나 순차적이지 않으면 수정
            if number != current_number:
                # 올바른 번호로 교체
                fixed_line = f"{indent}{current_number}. {content}"
                fixed_lines.append(fixed_line)
                if number != current_number:
                    logger.info(f"번호 매기기 수정: {number}. → {current_number}.")
                current_number += 1
                in_numbered_section = True
            else:
                # 올바른 번호면 그대로 사용
                fixed_lines.append(line)
                current_number += 1
                in_numbered_section = True
        else:
            # 번호가 없는 줄
            # 빈 줄이나 섹션 구분(---, === 등)이면 번호 리셋 고려
            stripped = line.strip()
            if not stripped or stripped.startswith('---') or stripped.startswith('==='):
                # 빈 줄이나 구분선이면 번호 리셋
                if in_numbered_section:
                    current_number = 1
                    in_numbered_section = False
            fixed_lines.append(line)
    
    fixed_text = '\n'.join(fixed_lines)
    
    # 수정이 있었는지 확인
    if fixed_text != text:
        logger.warning("⚠️ 번호 매기기가 수정되었습니다.")
    
    return fixed_text


def _get_writer_llm():
    """Writer LLM 인스턴스 생성"""
    return ChatOpenAI(**config.get_writer_llm_config())


@traceable(name="writer", run_type="llm")
async def writer(state: ChatState):
    """Writer: 답변 종합/작성"""
    print("="*60, file=sys.stdout, flush=True)
    print("Writer 노드 시작: 최종 답변 작성", file=sys.stdout, flush=True)
    print("="*60, file=sys.stdout, flush=True)
    
    ensure_logger_setup()
    logger.info("="*60)
    logger.info("Writer 노드 시작")
    
    session_id = state.get("session_id", "default")
    current_messages = state.get("messages", [])
    db_search_results = state.get("db_search_results", [])
    web_search_results = state.get("web_search_results", [])
    summarized_results = state.get("summarized_results", [])
    needs_deep_research = state.get("needs_deep_research", False)
    search_loop_count = state.get("search_loop_count", 0)
    grader_score = state.get("grader_score", 0.0)
    grader_feedback = state.get("grader_feedback", "")
    
    # 날짜 계산
    kst = timezone(timedelta(hours=9))
    current_datetime = datetime.now(kst)
    current_date_str = current_datetime.strftime("%Y년 %m월 %d일")
    current_date_iso = current_datetime.strftime("%Y-%m-%d")
    current_time_str = current_datetime.strftime("%H시 %M분")
    
    yesterday_datetime = current_datetime - timedelta(days=1)
    yesterday_date_str = yesterday_datetime.strftime("%Y년 %m월 %d일")
    yesterday_date_iso = yesterday_datetime.strftime("%Y-%m-%d")
    yesterday_date_short = yesterday_datetime.strftime("%Y.%m.%d")
    
    logger.info(f"입력: DB={len(db_search_results)}, 웹={len(web_search_results)}, 반복={search_loop_count}, 점수={grader_score:.2f}")
    
    # Fallback 처리
    is_fallback = search_loop_count >= 3
    
    # 검색 결과 선택 (원본 우선)
    if web_search_results:
        final_search_results = web_search_results
        processing_note = " (원본)"
    elif summarized_results:
        final_search_results = summarized_results
        processing_note = " (요약)"
    else:
        final_search_results = []
        processing_note = ""
    
    # 컨텍스트 구성
    context_parts = []
    
    if db_search_results:
        context_parts.append("=== FAQ 데이터베이스 검색 결과 ===\n")
        for i, result in enumerate(db_search_results, 1):
            context_parts.append(f"[FAQ {i}]\n{result.get('text', '')}\n")
    
    if is_fallback:
        context_parts.append("\n**⚠️ Fallback 모드:**\n")
        context_parts.append("3회 이상 검색했지만 신뢰할 수 있는 정보를 찾지 못했습니다.\n")
        if grader_feedback:
            context_parts.append(f"피드백: {grader_feedback}\n")
    
    if needs_deep_research or web_search_results:
        if final_search_results:
            context_parts.append(f"\n=== 웹 검색 결과{processing_note} ===\n")
            
            for i, result in enumerate(final_search_results, 1):
                title = result.get('title', '제목 없음')
                snippet = result.get('snippet', '')
                url = result.get('url', '')
                
                if snippet and len(snippet.strip()) > 10:
                    max_length = config.MAX_SNIPPET_LENGTH
                    context_parts.append(f"[검색 결과 {i}] {title}\n{snippet[:max_length]}{'...' if len(snippet) > max_length else ''}\n출처: {url}\n\n")
    
    context = "\n".join(context_parts) if context_parts else ""
    
    # 시세 비교 질문 감지
    user_query_for_comparison = ""
    if current_messages:
        user_msgs = [msg for msg in current_messages if isinstance(msg, HumanMessage)]
        if user_msgs:
            user_query_for_comparison = user_msgs[-1].content.lower()
    
    is_price_comparison = any(keyword in user_query_for_comparison for keyword in [
        '비교', '차이', '변화', '변동', '상승', '하락'
    ]) and any(keyword in user_query_for_comparison for keyword in config.PRICE_KEYWORDS)
    
    # 시스템 프롬프트 생성
    if is_fallback:
        has_search_results = len(web_search_results) > 0
        fallback_context = context if context else "검색 결과를 찾을 수 없습니다."
        
        if has_search_results:
            system_prompt_content = f"""
당신은 블록체인과 빗썸 이용 방법에 대하여 도와주는 친절한 챗봇입니다.

**중요: Fallback 모드 (검색 결과 있음)**
검색 결과가 {len(web_search_results)}개 있습니다. 최대한 활용하세요.

답변 규칙:
1. 검색 결과의 정보를 최대한 활용
2. 불완전해도 부분 정보 제공
3. 빗썸 공식 홈페이지: {config.BITHUMB_HOME_URL} 안내

{fallback_context}
"""
        else:
            system_prompt_content = f"""
당신은 블록체인과 빗썸 이용 방법에 대하여 도와주는 친절한 챗봇입니다.

**Fallback 모드**
신뢰할 수 있는 정보를 찾지 못했습니다.

답변 규칙:
1. "죄송합니다. 현재 신뢰할 수 있는 정보를 찾을 수 없습니다."
2. 빗썸 공식 홈페이지: {config.BITHUMB_HOME_URL} 안내

{fallback_context}
"""
    else:
        base_prompt = get_system_prompt_template().format(
            context=context if context else "추가 참고 자료가 없습니다.",
            current_date_str=current_date_str,
            current_date_iso=current_date_iso,
            current_time_str=current_time_str,
            yesterday_date_str=yesterday_date_str,
            yesterday_date_iso=yesterday_date_iso,
            yesterday_date_short=yesterday_date_short,
            bithumb_home_url=config.BITHUMB_HOME_URL,
            link_rules_prompt=config.get_link_rules_prompt()
        )
        
        if is_price_comparison:
            comparison_instruction = get_price_comparison_instruction().format(
                yesterday_date_str=yesterday_date_str,
                yesterday_date_iso=yesterday_date_iso
            )
            system_prompt_content = base_prompt + comparison_instruction
        else:
            system_prompt_content = base_prompt
    
    system_prompt = SystemMessage(content=system_prompt_content)
    
    # 메시지 구성
    filtered_messages = [msg for msg in current_messages if not isinstance(msg, AIMessage) or "[웹 검색 완료]" not in msg.content]
    all_messages = [system_prompt] + filtered_messages
    
    try:
        writer_llm = _get_writer_llm()
        fallback_note = " (Fallback)" if is_fallback else ""
        logger.info(f"LLM 호출{fallback_note}")
        
        response = await writer_llm.ainvoke(all_messages)
        response_text = response.content if hasattr(response, "content") else str(response)
        
        # JSON 구조 제거 (내부 처리 정보가 응답에 포함된 경우)
        # {"search_queries":[...], "research_plan":"...", "priority":1} 같은 구조 제거
        # {"score":0.8, "is_sufficient":true, "feedback":"..."} 같은 구조도 제거
        import re
        
        original_text = response_text
        result = response_text.strip()
        
        # JSON 키워드 목록 (모든 내부 처리 정보)
        json_keywords = [
            '"search_queries"', '"research_plan"', '"priority"',
            '"score"', '"is_sufficient"', '"feedback"', '"missing_information"',
            'search_queries', 'research_plan', 'priority',
            'score', 'is_sufficient', 'feedback', 'missing_information'
        ]
        
        # 방법 1: 정규식으로 모든 JSON 블록을 한 번에 제거 시도
        # {로 시작해서 }로 끝나는 블록 중 JSON 키워드를 포함하는 것
        json_pattern = r'\{[^{}]*(?:"search_queries"|"research_plan"|"priority"|"score"|"is_sufficient"|"feedback"|"missing_information")[^{}]*?\}'
        result = re.sub(json_pattern, '', result, flags=re.DOTALL)
        
        # 방법 2: 반복적으로 JSON 블록 제거 (연속된 JSON 처리)
        max_iterations = 20
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            json_start = result.find('{')
            if json_start == -1:
                break
            
            # JSON 키워드 확인 (처음 3000자 내)
            check_range = result[json_start:min(json_start + 3000, len(result))]
            has_json_keyword = any(keyword in check_range for keyword in json_keywords)
            
            if not has_json_keyword:
                # JSON 키워드가 없으면 다음 { 찾기
                next_start = result.find('{', json_start + 1)
                if next_start == -1:
                    break
                json_start = next_start
                check_range = result[json_start:min(json_start + 3000, len(result))]
                has_json_keyword = any(keyword in check_range for keyword in json_keywords)
                if not has_json_keyword:
                    break
            
            # 매칭되는 } 찾기 (중첩된 중괄호 고려)
            brace_count = 0
            end_idx = json_start
            found_end = False
            
            for i in range(json_start, min(len(result), json_start + 5000)):  # 최대 5000자까지 확인
                if result[i] == '{':
                    brace_count += 1
                elif result[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        found_end = True
                        break
            
            if not found_end:
                # }를 찾지 못하면 첫 번째 } 사용
                first_close = result.find('}', json_start)
                if first_close != -1:
                    end_idx = first_close + 1
                else:
                    break
            
            # JSON 블록 제거
            before = result[:json_start].rstrip()
            after = result[end_idx:].lstrip()
            after = re.sub(r'^\s*\n\s*\n\s*', '', after)  # 여러 줄바꿈 제거
            
            if before:
                result = before + ('\n\n' if before and after else '') + after
            else:
                result = after
            
            result = result.strip()
            
            # 더 이상 JSON 키워드가 없으면 종료
            if not any(keyword in result for keyword in json_keywords):
                break
        
        # 연속된 공백과 줄바꿈 정리
        result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
        result = result.strip()
        
        # JSON이 제거되었는지 확인
        if result != original_text:
            logger.warning(f"⚠️ JSON 구조가 응답에서 제거되었습니다. (원본 길이: {len(original_text)}, 정리 후: {len(result)})")
            response_text = result
        
        # 최종 검증: JSON 키워드가 여전히 남아있으면 강제 제거
        if any(keyword in response_text for keyword in json_keywords):
            logger.error("❌ JSON 키워드가 여전히 응답에 포함되어 있습니다. 강제 제거 시도...")
            # 최후의 수단: 모든 {로 시작하는 블록을 강제로 제거 (JSON 키워드가 있는 경우만)
            while '{' in response_text:
                json_start = response_text.find('{')
                if json_start == -1:
                    break
                
                # JSON 키워드 확인
                check_range = response_text[json_start:min(json_start + 3000, len(response_text))]
                if not any(keyword in check_range for keyword in json_keywords):
                    # JSON 키워드가 없으면 다음 { 찾기
                    next_start = response_text.find('{', json_start + 1)
                    if next_start == -1:
                        break
                    json_start = next_start
                    check_range = response_text[json_start:min(json_start + 3000, len(response_text))]
                    if not any(keyword in check_range for keyword in json_keywords):
                        break
                
                # 매칭되는 } 찾기
                brace_count = 0
                end_idx = json_start
                for i in range(json_start, min(len(response_text), json_start + 5000)):
                    if response_text[i] == '{':
                        brace_count += 1
                    elif response_text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                
                if end_idx > json_start:
                    before = response_text[:json_start].rstrip()
                    after = response_text[end_idx:].lstrip()
                    after = re.sub(r'^\s*\n\s*\n\s*', '', after)
                    response_text = (before + ('\n\n' if before and after else '') + after).strip()
                else:
                    break
            
            logger.warning("⚠️ 모든 JSON 블록을 강제로 제거했습니다.")
        
        # 번호 매기기 검증 및 수정
        response_text = _fix_numbering(response_text)
        
        # response 객체의 content를 업데이트 (스트리밍에 반영되도록)
        if hasattr(response, "content"):
            response.content = response_text
        else:
            # AIMessage 객체 생성 (이미 상단에서 import됨)
            response = AIMessage(content=response_text)
        
        # Fallback 모드 검증
        if is_fallback:
            fallback_keywords = ['확인할 수 없', '찾을 수 없', '정보를 찾을 수 없', '죄송합니다']
            has_fallback_keyword = any(keyword in response_text for keyword in fallback_keywords)
            is_too_long = len(response_text) > 200
            
            if not has_fallback_keyword or is_too_long:
                logger.warning(f"⚠️ Fallback 부적절 답변 (길이: {len(response_text)}자)")
                response_text = (
                    "죄송합니다. 현재 신뢰할 수 있는 정보를 찾을 수 없습니다.\n\n"
                    f"빗썸 공식 홈페이지: {config.BITHUMB_HOME_URL} 에서 직접 확인하시기 바랍니다.\n\n"
                    f"고객지원 페이지: {config.BITHUMB_SUPPORT_URL}"
                )
                response = AIMessage(content=response_text)
        
        print(f"[Writer] ✅ 완료 (길이: {len(response_text)}자)", file=sys.stdout, flush=True)
        logger.info(f"✅ Writer 완료 (길이: {len(response_text)}자)")
        logger.info("="*60)
        print("="*60, file=sys.stdout, flush=True)
        
        # session_id를 명시적으로 포함하여 반환 (web_search 경로에서 세션 ID 유지)
        return {
            "messages": [response],
            "session_id": session_id  # 세션 ID 명시적으로 포함
        }
    except Exception as e:
        logger.info("="*60)
        return handle_node_error(e, "writer", state)

