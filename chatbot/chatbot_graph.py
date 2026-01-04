"""
하위 호환성을 위한 래퍼 모듈
실제 구현은 chatbot/graph.py에 있습니다.

주의: 이 파일은 기존 코드와의 호환성을 위해 유지됩니다.
새 코드에서는 chatbot.graph를 직접 import하세요.
"""
# 모든 기능을 graph.py에서 re-export
from .graph import (
    create_chatbot_graph,
    get_chatbot_graph,
    chatbot_graph,
    initialize_graph,
)

__all__ = [
    'create_chatbot_graph',
    'get_chatbot_graph',
    'chatbot_graph',
    'initialize_graph',
]
