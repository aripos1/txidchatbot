"""
채팅 데이터 AI 분석 모듈
사용자 메시지를 분석하여 감정, 의도, 인사이트를 추출
"""
import json
import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..configuration import config

logger = logging.getLogger(__name__)


async def analyze_chat_with_ai(
    user_messages: List[Dict[str, Any]], 
    basic_stats: Dict[str, Any]
) -> Dict[str, Any]:
    """
    AI를 사용한 메시지 내용 심층 분석
    
    Args:
        user_messages: 사용자 메시지 리스트
        basic_stats: 기본 통계 정보
        
    Returns:
        AI 분석 결과 딕셔너리
    """
    try:
        if not config.OPENAI_API_KEY:
            logger.warning("OpenAI API 키가 없어 AI 분석을 건너뜁니다.")
            return {"ai_error": "OpenAI API 키가 설정되지 않았습니다."}
        
        if len(user_messages) == 0:
            logger.warning("분석할 메시지가 없습니다.")
            return {"ai_error": "분석할 메시지가 없습니다."}
        
        # 최근 100개 메시지만 샘플링 (비용 절감)
        sample_messages = user_messages[-100:] if len(user_messages) > 100 else user_messages
        messages_text = "\n".join([f"- {msg.get('content', '')[:200]}" for msg in sample_messages[:50]])
        
        if not messages_text.strip():
            logger.warning("분석할 메시지 내용이 비어있습니다.")
            return {"ai_error": "분석할 메시지 내용이 없습니다."}
        
        # AI 분석 프롬프트
        analysis_prompt = f"""다음은 블록체인 트랜잭션 조회 서비스의 사용자 채팅 메시지 샘플입니다.

메시지 샘플:
{messages_text}

기본 통계:
- 전체 메시지 수: {basic_stats.get('total_user_messages', 0)}
- 질문 유형: {list(basic_stats.get('question_types', {}).keys())}
- 언급된 네트워크: {list(basic_stats.get('blockchain_networks', {}).keys())}

다음 JSON 형식으로 분석 결과를 반환해주세요:
{{
    "sentiment_analysis": {{
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "overall_sentiment": "neutral"
    }},
    "intent_categories": {{
        "transaction_lookup": 0,
        "price_inquiry": 0,
        "technical_question": 0,
        "general_inquiry": 0,
        "error_report": 0
    }},
    "user_needs": [
        "사용자가 가장 많이 요청하는 기능이나 정보"
    ],
    "insights": [
        "주요 인사이트 3-5개"
    ],
    "recommendations": [
        "서비스 개선 제안 2-3개"
    ]
}}

한국어로 응답해주세요."""

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=config.OPENAI_API_KEY
        )
        
        messages = [
            SystemMessage(content="당신은 사용자 채팅 데이터를 분석하는 전문가입니다. JSON 형식으로만 응답하세요."),
            HumanMessage(content=analysis_prompt)
        ]
        
        logger.info("OpenAI API 호출 중...")
        response = await llm.ainvoke(messages)
        response_text = response.content.strip()
        logger.info(f"AI 응답 수신 완료 (길이: {len(response_text)})")
        
        # JSON 추출 (마크다운 코드 블록 제거)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        # JSON 파싱
        try:
            ai_analysis = json.loads(response_text)
            logger.info("AI 분석 결과 파싱 성공")
        except json.JSONDecodeError as e:
            logger.error(f"AI 분석 응답 JSON 파싱 실패: {e}")
            logger.error(f"응답 내용 (처음 500자): {response_text[:500]}")
            # JSON 파싱 실패 시에도 부분적으로 추출 시도
            return {
                "ai_error": f"JSON 파싱 실패: {str(e)}",
                "ai_raw_response": response_text[:200]
            }
        
        result = {
            "ai_sentiment": ai_analysis.get("sentiment_analysis", {}),
            "ai_intent_categories": ai_analysis.get("intent_categories", {}),
            "ai_user_needs": ai_analysis.get("user_needs", []),
            "ai_insights": ai_analysis.get("insights", []),
            "ai_recommendations": ai_analysis.get("recommendations", [])
        }
        
        logger.info(f"AI 분석 완료: 감정={bool(result.get('ai_sentiment'))}, 인사이트={len(result.get('ai_insights', []))}개")
        return result
        
    except Exception as e:
        logger.error(f"AI 분석 실패: {e}", exc_info=True)
        return {"ai_error": f"AI 분석 중 오류 발생: {str(e)}"}
