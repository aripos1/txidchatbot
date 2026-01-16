// Chatbot JavaScript - Extracted from chatbot.html
// 노드 표시 이름 매핑 (공통)
const NODE_DISPLAY_NAMES = {
    "router": "🔀 라우팅 중...",
    "simple_chat_specialist": "💬 응답 생성 중...",
    "faq_specialist": "📚 FAQ 검색 중...",
    "transaction_specialist": "🔍 트랜잭션 조회 중...",
    "planner": "📋 검색 계획 중...",
    "researcher": "🔎 웹 검색 중...",
    "grader": "📊 결과 평가 중...",
    "writer": "✍️ 응답 작성 중...",
    "intent_clarifier": "🤔 의도 확인 중...",
    "save_response": "💾 저장 중..."
};

// 노드 이름을 "생각하는 과정" 제목으로 변환
function getNodeStepTitle(nodeName, displayName) {
    const nodeTitleMap = {
        'router': '🔀 라우팅',
        'faq_specialist': '📚 FAQ 검색',
        'transaction_specialist': '🔍 트랜잭션 조회',
        'planner': '📋 검색 계획 수립',
        'researcher': '🔎 웹 검색',
        'grader': '📊 결과 평가',
        'writer': '✍️ 응답 작성',
        'intent_clarifier': '🤔 의도 확인',
        'save_response': '💾 저장'
    };
    
    return nodeTitleMap[nodeName] || displayName || null;
}

// "생각하는 과정" 제목에서 노드 이름 추출
function getNodeNameFromStep(stepTitle) {
    const titleToNodeMap = {
        '🔀 라우팅': 'router',
        '📚 FAQ 검색': 'faq_specialist',
        '🔍 트랜잭션 조회': 'transaction_specialist',
        '📋 검색 계획 수립': 'planner',
        '🔎 웹 검색': 'researcher',
        '📊 결과 평가': 'grader',
        '✍️ 응답 작성': 'writer',
        '🤔 의도 확인': 'intent_clarifier',
        '💾 저장': 'save_response'
    };
    
    return titleToNodeMap[stepTitle] || null;
}

// JSON을 사용자 친화적인 "생각하는 과정"으로 변환
function parseThinkingProcess(jsonText) {
    try {
        const json = JSON.parse(jsonText);
        const steps = [];
        
        // Planner 노드 정보
        if (json.search_queries || json.research_plan || json.priority) {
            steps.push({
                title: '📋 검색 계획 수립',
                content: json.research_plan || '검색 계획을 수립하고 있습니다.',
                queries: json.search_queries || []
            });
        }
        
        // Grader 노드 정보
        if (json.score !== undefined || json.is_sufficient !== undefined || json.feedback) {
            const score = json.score || 0;
            const isSufficient = json.is_sufficient || false;
            const feedback = json.feedback || '';
            
            steps.push({
                title: `📊 결과 평가 (점수: ${(score * 100).toFixed(0)}%)`,
                content: feedback || (isSufficient ? '검색 결과가 충분합니다.' : '추가 검색이 필요합니다.'),
                score: score,
                isSufficient: isSufficient
            });
        }
        
        return steps;
    } catch (e) {
        return [];
    }
}

// "생각하는 과정" UI 생성 (간소화)
function createThinkingProcessUI(steps) {
    // 단계가 있으면 표시 (content가 없어도 노드 이름은 표시)
    if (steps.length === 0) return null;
    
    const container = document.createElement('div');
    container.className = 'thinking-process collapsed';
    
    const header = document.createElement('div');
    header.className = 'thinking-header';
    header.innerHTML = `
        <div class="thinking-title">
            <span>🤔 생각하는 과정 (${steps.length}단계)</span>
        </div>
        <span class="thinking-toggle">▼</span>
    `;
    
    const content = document.createElement('div');
    content.className = 'thinking-content';
    
    steps.forEach(step => {
        const stepDiv = document.createElement('div');
        stepDiv.className = 'thinking-step';
        
        let stepHTML = `<div class="thinking-step-title">${step.title}</div>`;
        if (step.content) {
            stepHTML += `<div class="thinking-step-content">${step.content}</div>`;
        }
        
        // 검색 결과 링크 추가
        if (step.searchInfo) {
            const searchInfo = step.searchInfo;
            const links = [];
            
            // DB 검색 결과 링크
            if (searchInfo.db_results && searchInfo.db_results.length > 0) {
                searchInfo.db_results.forEach((result, idx) => {
                    if (result.url) {
                        links.push(`<a href="${result.url}" target="_blank" rel="noopener noreferrer" class="thinking-link">${result.title || 'FAQ 결과 ' + (idx + 1)}</a>`);
                    }
                });
            }
            
            // 웹 검색 결과 링크
            if (searchInfo.web_results && searchInfo.web_results.length > 0) {
                searchInfo.web_results.forEach((result, idx) => {
                    if (result.url) {
                        const title = result.title || '웹 결과 ' + (idx + 1);
                        links.push(`<a href="${result.url}" target="_blank" rel="noopener noreferrer" class="thinking-link">${title}</a>`);
                    }
                });
            }
            
            if (links.length > 0) {
                stepHTML += `<div class="thinking-links">${links.join('')}</div>`;
            }
        }
        
        stepDiv.innerHTML = stepHTML;
        content.appendChild(stepDiv);
    });
    
    container.appendChild(header);
    container.appendChild(content);
    
    // 토글 기능
    header.addEventListener('click', () => {
        if (container.classList.contains('collapsed')) {
            container.classList.remove('collapsed');
            container.classList.add('expanded');
            header.querySelector('.thinking-toggle').textContent = '▲';
        } else {
            container.classList.remove('expanded');
            container.classList.add('collapsed');
            header.querySelector('.thinking-toggle').textContent = '▼';
        }
    });
    
    return container;
}

// 세션 ID 생성 (브라우저 세션당 고유)
let sessionId = sessionStorage.getItem('chatSessionId') || generateSessionId();
if (!sessionStorage.getItem('chatSessionId')) {
    sessionStorage.setItem('chatSessionId', sessionId);
}

function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// 페이지 로드 시 대화 기록 불러오기
let isHistoryLoaded = false;

window.addEventListener('DOMContentLoaded', async () => {
    if (!isHistoryLoaded) {
        isHistoryLoaded = true;
        await loadChatHistory();
    }
});

async function loadChatHistory() {
    try {
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.innerHTML = '';
        
        const response = await fetch(`/api/chat/history/${sessionId}`);
        const data = await response.json();
        
        if (data.history && data.history.length > 0) {
            const seenMessages = new Set();
            
            data.history.forEach(msg => {
                const messageKey = `${msg.role}:${msg.content}`;
                if (!seenMessages.has(messageKey)) {
                    seenMessages.add(messageKey);
                    addMessageToChat(msg.role, msg.content, false);
                }
            });
        }
    } catch (error) {
        // console.error('대화 기록 불러오기 실패:', error);
    }
}

// 스트리밍 모드 설정
const USE_STREAMING = true;
let currentAbortController = null;

async function sendMessage(event) {
    event.preventDefault();
    
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // 이전 요청 취소
    if (currentAbortController) {
        currentAbortController.abort();
    }
    currentAbortController = new AbortController();
    
    // 사용자 메시지 표시
    addMessageToChat('user', message);
    input.value = '';
    
    // 입력 비활성화
    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;
    
    if (USE_STREAMING) {
        await sendMessageStreaming(message, sendBtn);
    } else {
        await sendMessageNormal(message, sendBtn);
    }
    
    // 입력 필드로 포커스
    input.focus();
}

async function sendMessageStreaming(message, sendBtn) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = '<span class="streaming-cursor">▊</span>';
    
    messageDiv.appendChild(bubble);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // 사용자 질문을 응답에서 제거하기 위한 변수 저장
    const userMessageNormalized = message.trim().toLowerCase();
    
    let thinkingProcessUI = null;
    let thinkingSteps = [];
    let shouldShowThinkingProcess = false;
    let currentResponseNode = null;
    let nodeSearchInfo = {};
    
    let fullContent = '';
    let hasReceivedToken = false;
    let jsonBlocks = [];
    let nodeHistory = [];
    let doneReceived = false;  // done 이벤트 수신 여부 추적
    let finalResponseFromServer = '';  // done 이벤트의 final_response 저장
    
    // 검색 정보를 "생각하는 과정" 콘텐츠로 변환 (간소화 + 필수 정보 표시)
    function createThinkingStepContent(nodeName, nodeDisplay, searchInfo) {
        const queries = searchInfo.queries || [];
        const dbResults = searchInfo.db_results || [];
        const webResults = searchInfo.web_results || [];
        
        // faq_specialist의 경우 검색 정보가 없어도 노드 이름은 표시
        if (nodeName === 'faq_specialist') {
            if (queries.length === 0 && dbResults.length === 0 && webResults.length === 0) {
                return 'FAQ 검색 중...';
            }
        } else {
            if (queries.length === 0 && dbResults.length === 0 && webResults.length === 0) {
                return null;
            }
        }
        
        let contentParts = [];
        
        // 검색 쿼리 표시 (최대 3개, 간결하게)
        if (queries.length > 0) {
            const displayQueries = queries.slice(0, 3).map(q => {
                // 쿼리가 너무 길면 자르기 (최대 30자)
                return q.length > 30 ? q.substring(0, 30) + '...' : q;
            });
            const queryText = displayQueries.join(', ');
            const extraCount = queries.length - 3;
            contentParts.push(`🔍 ${queryText}${extraCount > 0 ? ` 외 ${extraCount}개` : ''}`);
        }
        
        // 검색 결과 표시 (주요 제목 1-2개 + 총 개수)
        const allResults = [...dbResults, ...webResults];
        if (allResults.length > 0) {
            const resultTitles = [];
            
            // 주요 결과 제목 1-2개 추출 (제목이 있는 것 우선)
            const resultsWithTitle = allResults.filter(r => r.title && r.title.trim());
            if (resultsWithTitle.length > 0) {
                resultsWithTitle.slice(0, 2).forEach(r => {
                    let title = r.title || r.text || '';
                    // 제목이 너무 길면 자르기 (최대 25자)
                    if (title.length > 25) {
                        title = title.substring(0, 25) + '...';
                    }
                    resultTitles.push(title);
                });
            }
            
            // 결과 요약 생성
            const resultSummary = [];
            if (dbResults.length > 0) resultSummary.push(`FAQ ${dbResults.length}개`);
            if (webResults.length > 0) resultSummary.push(`웹 ${webResults.length}개`);
            
            if (resultTitles.length > 0) {
                contentParts.push(`📚 ${resultTitles.join(', ')} (총 ${allResults.length}개)`);
            } else {
                contentParts.push(`📚 ${resultSummary.join(', ')}`);
            }
        }
        
        return contentParts.length > 0 ? contentParts.join(' • ') : null;
    }

    // "생각하는 과정" 단계 추가 또는 업데이트
    function addOrUpdateThinkingStep(nodeName, nodeDisplay, searchInfo) {
        if (!nodeName || nodeName === 'simple_chat_specialist' || nodeName === 'transaction_specialist') {
            return -1;
        }
        
        const stepTitle = getNodeStepTitle(nodeName, '');
        if (!stepTitle) {
            return -1;
        }
        
        let stepIndex = thinkingSteps.findIndex(step => {
            const stepNodeName = getNodeNameFromStep(step.title);
            return stepNodeName === nodeName;
        });
        
        if (stepIndex === -1) {
            if (!nodeHistory.some(n => n.name === nodeName)) {
                nodeHistory.push({
                    name: nodeName,
                    display: nodeDisplay || NODE_DISPLAY_NAMES[nodeName] || nodeName
                });
            }
            
            thinkingSteps.push({
                title: stepTitle,
                content: '',
                queries: [],
                searchInfo: {}
            });
            stepIndex = thinkingSteps.length - 1;
        }
        
        const content = createThinkingStepContent(nodeName, '', searchInfo);
        thinkingSteps[stepIndex].content = content;
        thinkingSteps[stepIndex].queries = searchInfo.queries || [];
        thinkingSteps[stepIndex].searchInfo = searchInfo;
        
        return stepIndex;
    }
    
    // "생각하는 과정" UI 업데이트 함수
    function updateThinkingProcessUI() {
        if (!thinkingProcessUI) {
            thinkingProcessUI = createThinkingProcessUI(thinkingSteps);
        } else {
            const content = thinkingProcessUI.querySelector('.thinking-content');
            if (content) {
                content.innerHTML = '';
                
                const header = thinkingProcessUI.querySelector('.thinking-header');
                if (header) {
                    const titleSpan = header.querySelector('.thinking-title span');
                    if (titleSpan) {
                        titleSpan.textContent = `🤔 생각하는 과정 (${thinkingSteps.length}단계)`;
                    }
                }
                
                thinkingSteps.forEach(step => {
                    const stepDiv = document.createElement('div');
                    stepDiv.className = 'thinking-step';
                    
                    let stepHTML = `<div class="thinking-step-title">${step.title}</div>`;
                    if (step.content) {
                        stepHTML += `<div class="thinking-step-content">${step.content}</div>`;
                    }
                    
                    // 검색 결과 링크 추가
                    if (step.searchInfo) {
                        const searchInfo = step.searchInfo;
                        const links = [];
                        
                        // DB 검색 결과 링크
                        if (searchInfo.db_results && searchInfo.db_results.length > 0) {
                            searchInfo.db_results.forEach((result, idx) => {
                                if (result.url) {
                                    links.push(`<a href="${result.url}" target="_blank" rel="noopener noreferrer" class="thinking-link">${result.title || 'FAQ 결과 ' + (idx + 1)}</a>`);
                                }
                            });
                        }
                        
                        // 웹 검색 결과 링크
                        if (searchInfo.web_results && searchInfo.web_results.length > 0) {
                            searchInfo.web_results.forEach((result, idx) => {
                                if (result.url) {
                                    const title = result.title || '웹 결과 ' + (idx + 1);
                                    links.push(`<a href="${result.url}" target="_blank" rel="noopener noreferrer" class="thinking-link">${title}</a>`);
                                }
                            });
                        }
                        
                        if (links.length > 0) {
                            stepHTML += `<div class="thinking-links">${links.join('')}</div>`;
                        }
                    }
                    
                    stepDiv.innerHTML = stepHTML;
                    content.appendChild(stepDiv);
                });
            }
        }
    }
    
    try {
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            }),
            signal: currentAbortController.signal
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';  // SSE 이벤트 버퍼 (불완전한 이벤트 보관)
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (value) {
                const chunk = decoder.decode(value, { stream: !done });
                buffer += chunk;
            }
            
            // SSE 이벤트는 \n\n로 구분됨
            let eventEnd = buffer.indexOf('\n\n');
            while (eventEnd !== -1) {
                const eventText = buffer.slice(0, eventEnd).trim();
                buffer = buffer.slice(eventEnd + 2);
                
                if (eventText) {
                    // 이벤트에서 data: 줄 찾기
                    const lines = eventText.split('\n');
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const jsonStr = line.slice(6);  // 'data: ' 제거
                                // console.log('[SSE] 라인 파싱 시도:', jsonStr.substring(0, 150));
                                const data = JSON.parse(jsonStr);
                                // console.log('[SSE] 이벤트 파싱 성공 - type:', data.type);
                                
                                    if (data.type === 'token') {
                                        // console.log('[TOKEN] 받음:', data.content.substring(0, 50) + '...');
                                        
                                        // 서버 프롬프트에서 이미 사용자 입력 반복을 방지하므로 필터링 불필요
                                        // 사용자 입력과 정확히 동일한 단독 토큰만 건너뛰기 (안전장치)
                                        const tokenContent = data.content.trim();
                                        if (tokenContent && 
                                            tokenContent.toLowerCase() === userMessageNormalized && 
                                            tokenContent.length === userMessageNormalized.length &&
                                            tokenContent === userMessageNormalized) {
                                            // 토큰이 사용자 입력과 정확히 일치하고, 단독 토큰인 경우에만 건너뛰기
                                            // console.log('[TOKEN] 사용자 입력과 정확히 동일한 토큰 감지 - 건너뜀:', tokenContent);
                                            continue;
                                        }
                                        
                                        // 그 외 모든 토큰은 그대로 사용 (서버 프롬프트가 처리하므로 추가 필터링 불필요)
                                        fullContent += data.content;
                                        
                                        // JSON 메타데이터 추출 (생각하는 과정용) - 표시는 하되 제거하지 않음
                                    let jsonStart = fullContent.indexOf('{');
                                    const foundJsonBlocks = [];
                                    
                                    while (jsonStart !== -1) {
                                        let braceCount = 0;
                                        let jsonEnd = -1;
                                        
                                        for (let i = jsonStart; i < fullContent.length; i++) {
                                            if (fullContent[i] === '{') braceCount++;
                                            if (fullContent[i] === '}') braceCount--;
                                            if (braceCount === 0) {
                                                jsonEnd = i + 1;
                                                break;
                                            }
                                        }
                                        
                                        if (jsonEnd > jsonStart) {
                                            const jsonText = fullContent.substring(jsonStart, jsonEnd);
                                            
                                            // JSON 메타데이터 키워드가 포함된 경우만 처리
                                            if (jsonText.includes('"search_queries"') || 
                                                jsonText.includes('"research_plan"') || 
                                                jsonText.includes('"priority"') ||
                                                jsonText.includes('"score"') || 
                                                jsonText.includes('"is_sufficient"') || 
                                                jsonText.includes('"feedback"') ||
                                                jsonText.includes('"missing_information"')) {
                                                
                                                try {
                                                    const parsed = JSON.parse(jsonText);
                                                    const isNew = !foundJsonBlocks.some(block => block.text === jsonText);
                                                    
                                                    if (isNew) {
                                                        foundJsonBlocks.push({ text: jsonText, parsed: parsed });
                                                        const alreadyExists = jsonBlocks.some(block => block.text === jsonText);
                                                        if (!alreadyExists) {
                                                            jsonBlocks.push({ text: jsonText, parsed: parsed });
                                                            
                                                            const steps = parseThinkingProcess(jsonText);
                                                            if (steps.length > 0) {
                                                                thinkingSteps.push(...steps);
                                                                shouldShowThinkingProcess = true;
                                                                if (!thinkingProcessUI) {
                                                                    thinkingProcessUI = createThinkingProcessUI(thinkingSteps);
                                                                } else {
                                                                    updateThinkingProcessUI();
                                                                }
                                                            }
                                                        }
                                                    }
                                                } catch (e) {
                                                    // JSON 파싱 실패는 무시 (일반 텍스트일 수 있음)
                                                }
                                            }
                                            
                                            jsonStart = fullContent.indexOf('{', jsonEnd);
                                        } else {
                                            break;
                                        }
                                    }
                                    
                                    // 표시할 내용: JSON 메타데이터 블록만 제거하고 실제 응답은 유지
                                    let displayContent = fullContent;
                                    
                                    // JSON 메타데이터 블록만 제거 (jsonBlocks에 저장된 것들)
                                    const sortedBlocks = [...jsonBlocks].sort((a, b) => b.text.length - a.text.length);
                                    sortedBlocks.forEach(jsonBlock => {
                                        const escapedText = jsonBlock.text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                                        // 정확히 일치하는 JSON 블록만 제거
                                        displayContent = displayContent.replace(new RegExp(escapedText.replace(/\s+/g, '\\s+'), 'g'), '').trim();
                                    });
                                    
                                    // 앞쪽에 남아있는 JSON 패턴 제거 (응답 시작 부분의 메타데이터)
                                    displayContent = displayContent.replace(/^\s*\{[^{}]*?"(?:search_queries|research_plan|priority|score|is_sufficient|feedback|missing_information)"[^{}]*?\}\s*/g, '');
                                    
                                    // 빈 문자열이 아닌 경우에만 표시
                                    if (displayContent.trim() || fullContent.trim()) {
                                        hasReceivedToken = true;
                                        // displayContent가 비어있으면 원본 표시 (필터링 오류 방지)
                                        const contentToDisplay = displayContent.trim() || fullContent;
                                        const formattedContent = formatMessage(contentToDisplay);
                                        bubble.innerHTML = formattedContent + '<span class="streaming-cursor">▊</span>';
                                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                                    }
                                } else if (data.type === 'content') {
                            fullContent += data.content;
                            hasReceivedToken = true;
                            const formattedContent = formatMessage(fullContent);
                            bubble.innerHTML = formattedContent + '<span class="streaming-cursor">▊</span>';
                            messagesContainer.scrollTop = messagesContainer.scrollHeight;
                        } else if (data.type === 'node') {
                            const nodeName = data.node || '';
                            const displayName = data.display || '';
                            
                            // 노드 이벤트를 받으면 실시간으로 상태 업데이트
                            // 현재 응답이 시작되지 않았거나 비어있으면 상태만 표시
                            if (!hasReceivedToken || fullContent.trim() === '') {
                                bubble.innerHTML = `<div class="node-status-container"><span class="node-status">${displayName}</span><span class="streaming-cursor">▊</span></div>`;
                                messagesContainer.scrollTop = messagesContainer.scrollHeight;
                            }
                            
                            // 노드 히스토리에 추가
                            if (nodeName && !nodeHistory.some(n => n.name === nodeName)) {
                                nodeHistory.push({
                                    name: nodeName,
                                    display: displayName
                                });
                            }
                            
                            // faq_specialist의 경우 node 이벤트만으로도 "생각하는 과정"에 추가
                            if (nodeName === 'faq_specialist') {
                                const searchInfo = nodeSearchInfo[nodeName] || {};
                                const stepIndex = addOrUpdateThinkingStep(nodeName, displayName, searchInfo);
                                
                                if (stepIndex !== -1) {
                                    shouldShowThinkingProcess = true;
                                    updateThinkingProcessUI();
                                }
                            } else {
                                const searchInfo = nodeSearchInfo[nodeName] || {};
                                const stepIndex = addOrUpdateThinkingStep(nodeName, displayName, searchInfo);
                                
                                if (stepIndex !== -1) {
                                    shouldShowThinkingProcess = true;
                                    updateThinkingProcessUI();
                                }
                            }
                            
                            if (nodeName && ['writer', 'faq_specialist', 'transaction_specialist', 'intent_clarifier', 'simple_chat_specialist'].includes(nodeName)) {
                                currentResponseNode = nodeName;
                            }
                        } else if (data.type === 'node_search') {
                            const nodeName = data.node || '';
                            const searchInfo = data.search_info || {};
                            
                            // node_search 이벤트 로깅
                            // console.log('[NODE_SEARCH] 받음:', nodeName, searchInfo);
                            
                            if (nodeName === 'simple_chat_specialist' || nodeName === 'transaction_specialist') {
                                continue;  // return -> continue: 같은 청크의 다른 이벤트 처리 계속
                            }
                            
                            // nodeSearchInfo에 저장 (나중에 thinkingSteps에 추가됨)
                            nodeSearchInfo[nodeName] = searchInfo;
                            
                            // 즉시 thinkingSteps에 추가하여 업데이트
                            const nodeDisplay = nodeHistory.find(n => n.name === nodeName)?.display || NODE_DISPLAY_NAMES[nodeName] || nodeName;
                            const stepIndex = addOrUpdateThinkingStep(nodeName, nodeDisplay, searchInfo);
                            
                            if (stepIndex !== -1) {
                                shouldShowThinkingProcess = true;
                                
                                // thinkingProcessUI가 없으면 생성, 있으면 업데이트
                                if (!thinkingProcessUI) {
                                    thinkingProcessUI = createThinkingProcessUI(thinkingSteps);
                                    if (thinkingProcessUI && !messageDiv.contains(thinkingProcessUI)) {
                                        messageDiv.appendChild(thinkingProcessUI);
                                        thinkingProcessUI.classList.add('collapsed');
                                    }
                                } else {
                                    updateThinkingProcessUI();
                                }
                            }
                        } else if (data.type === 'done') {
                            // console.log('[DONE] 이벤트 수신:', { fullContent: fullContent.length, final_response: data.final_response?.length });
                            doneReceived = true;  // done 이벤트 수신 표시
                            
                            // final_response 저장 (fallback 처리용)
                            if (data.final_response) {
                                finalResponseFromServer = data.final_response;
                            }
                            
                            // 최종 응답: fullContent 우선, 없으면 final_response 사용
                            let finalText = fullContent.trim() || data.final_response || '';
                            
                            // 서버 프롬프트에서 이미 사용자 입력 반복을 방지하므로 필터링 불필요
                            // 최소한의 안전장치: 사용자 입력과 정확히 동일한 응답만 필터링 (거의 발생하지 않음)
                            if (userMessageNormalized && finalText.trim().toLowerCase() === userMessageNormalized) {
                                // 응답이 사용자 입력과 정확히 동일한 경우만 필터링 (서버 오류 방지)
                                // console.warn('[DONE] 사용자 입력과 정확히 동일한 응답 감지 - 건너뜀:', finalText);
                                finalText = ''; // 빈 응답으로 처리
                            }
                            
                            // JSON 메타데이터 블록만 제거
                            if (jsonBlocks.length > 0) {
                                const sortedBlocks = [...jsonBlocks].sort((a, b) => b.text.length - a.text.length);
                                sortedBlocks.forEach(jsonBlock => {
                                    const escapedText = jsonBlock.text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                                    finalText = finalText.replace(new RegExp(escapedText.replace(/\s+/g, '\\s+'), 'g'), '').trim();
                                });
                            }
                            
                            // 앞쪽에 남아있는 JSON 메타데이터 패턴 제거
                            finalText = finalText.replace(/^\s*\{[^{}]*?"(?:search_queries|research_plan|priority|score|is_sufficient|feedback|missing_information)"[^{}]*?\}\s*/g, '').trim();
                            
                            // 최종 텍스트가 비어있지 않은 경우에만 표시
                            // streaming-cursor 제거 (중요!)
                            // console.log('[DONE] 처리 시작:', { finalText: finalText.length, fullContent: fullContent.length, final_response: data.final_response?.length });
                            
                            if (finalText.trim()) {
                                const formattedContent = formatMessage(finalText);
                                bubble.innerHTML = formattedContent;  // streaming-cursor 제거됨
                                // console.log('[DONE] finalText로 표시 완료');
                            } else if (fullContent.trim()) {
                                // 필터링으로 인해 비어졌다면 원본 표시
                                const formattedContent = formatMessage(fullContent);
                                bubble.innerHTML = formattedContent;  // streaming-cursor 제거됨
                                // console.log('[DONE] fullContent로 표시 완료');
                            } else if (data.final_response && data.final_response.trim()) {
                                // final_response 사용 (token 이벤트를 받지 못한 경우)
                                const formattedContent = formatMessage(data.final_response.trim());
                                bubble.innerHTML = formattedContent;
                                fullContent = data.final_response;  // 나중에 사용할 수 있도록 저장
                                // console.log('[DONE] final_response로 표시 완료');
                            } else {
                                // 응답이 없어도 streaming-cursor 제거
                                bubble.innerHTML = '<span style="color: var(--text-secondary);">응답을 생성하지 못했습니다.</span>';
                                // console.warn('[DONE] 응답이 없음');
                            }
                            
                            // 스크롤 업데이트
                            messagesContainer.scrollTop = messagesContainer.scrollHeight;
                            
                            if (currentResponseNode === 'simple_chat_specialist' || currentResponseNode === 'transaction_specialist') {
                                shouldShowThinkingProcess = false;
                            } else {
                                // nodeSearchInfo에 있는 노드들을 thinkingSteps에 추가 (아직 추가되지 않은 경우)
                                const filteredNodeSearchInfo = Object.fromEntries(
                                    Object.entries(nodeSearchInfo).filter(([nodeName]) => 
                                        nodeName !== 'simple_chat_specialist' && nodeName !== 'transaction_specialist'
                                    )
                                );
                                
                                // nodeSearchInfo에 있지만 thinkingSteps에 없는 노드 추가
                                Object.entries(filteredNodeSearchInfo).forEach(([nodeName, searchInfo]) => {
                                    const stepIndex = thinkingSteps.findIndex(step => {
                                        const stepNodeName = getNodeNameFromStep(step.title);
                                        return stepNodeName === nodeName;
                                    });
                                    
                                    if (stepIndex === -1) {
                                        const stepTitle = getNodeStepTitle(nodeName, '');
                                        if (stepTitle) {
                                            const nodeDisplay = nodeHistory.find(n => n.name === nodeName)?.display || NODE_DISPLAY_NAMES[nodeName] || nodeName;
                                            addOrUpdateThinkingStep(nodeName, nodeDisplay, searchInfo);
                                        }
                                    } else {
                                        // 이미 있는 경우 searchInfo 업데이트
                                        const content = createThinkingStepContent(nodeName, '', searchInfo);
                                        thinkingSteps[stepIndex].content = content || thinkingSteps[stepIndex].content;
                                        thinkingSteps[stepIndex].queries = searchInfo.queries || thinkingSteps[stepIndex].queries;
                                        thinkingSteps[stepIndex].searchInfo = searchInfo;
                                    }
                                });
                                
                                // thinkingSteps가 있거나 nodeSearchInfo가 있으면 무조건 표시
                                if (thinkingSteps.length > 0 || Object.keys(filteredNodeSearchInfo).length > 0) {
                                    shouldShowThinkingProcess = true;
                                    
                                    // thinkingSteps가 비어있으면 nodeSearchInfo에서 생성
                                    if (thinkingSteps.length === 0 && Object.keys(filteredNodeSearchInfo).length > 0) {
                                        Object.entries(filteredNodeSearchInfo).forEach(([nodeName, searchInfo]) => {
                                            const stepTitle = getNodeStepTitle(nodeName, '');
                                            if (stepTitle) {
                                                const nodeDisplay = nodeHistory.find(n => n.name === nodeName)?.display || NODE_DISPLAY_NAMES[nodeName] || nodeName;
                                                addOrUpdateThinkingStep(nodeName, nodeDisplay, searchInfo);
                                            }
                                        });
                                    }
                                    
                                    if (!thinkingProcessUI && thinkingSteps.length > 0) {
                                        thinkingProcessUI = createThinkingProcessUI(thinkingSteps);
                                        if (thinkingProcessUI && !messageDiv.contains(thinkingProcessUI)) {
                                            messageDiv.appendChild(thinkingProcessUI);
                                        }
                                    } else if (thinkingProcessUI) {
                                        updateThinkingProcessUI();
                                    }
                                    
                                    if (thinkingProcessUI && !messageDiv.contains(thinkingProcessUI)) {
                                        messageDiv.appendChild(thinkingProcessUI);
                                    }
                                    
                                    if (thinkingProcessUI) {
                                        thinkingProcessUI.classList.add('collapsed');
                                        thinkingProcessUI.classList.remove('expanded');
                                    }
                                    
                                    /*
                                    console.log('[DONE] 생각하는 과정 표시:', {
                                        thinkingSteps: thinkingSteps.length,
                                        nodeSearchInfo: Object.keys(filteredNodeSearchInfo).length,
                                        shouldShow: shouldShowThinkingProcess
                                    });
                                    */
                                } else {
                                    // 정보가 없어도 최소한 표시 (디버깅용)
                                    /*
                                    console.warn('[DONE] 생각하는 과정 정보 없음:', {
                                        thinkingSteps: thinkingSteps.length,
                                        nodeSearchInfo: Object.keys(nodeSearchInfo).length
                                    });
                                    */
                                }
                            }
                            
                            sendBtn.disabled = false;
                        } else if (data.type === 'error') {
                            bubble.innerHTML = formatMessage('죄송합니다. 오류가 발생했습니다: ' + data.content);
                            sendBtn.disabled = false;
                        }
                            } catch (parseError) {
                                // console.error('[SSE] JSON 파싱 오류:', parseError, 'jsonStr:', jsonStr.substring(0, 100));
                            }
                        }
                    }
                }
                
                eventEnd = buffer.indexOf('\n\n');
            }
            
            // done이면 남은 버퍼 처리
            if (done) {
                // 남은 버퍼에서 완전한 이벤트 처리
                if (buffer.trim()) {
                    // console.log('[SSE] done - 남은 버퍼 처리:', buffer.substring(0, 200));
                    // 마지막 버퍼에서 이벤트 찾기
                    const lastEventEnd = buffer.indexOf('\n\n');
                    if (lastEventEnd !== -1) {
                        const lastEventText = buffer.slice(0, lastEventEnd).trim();
                        buffer = buffer.slice(lastEventEnd + 2);
                        
                        if (lastEventText) {
                            const lines = lastEventText.split('\n');
                            for (const line of lines) {
                                if (line.startsWith('data: ')) {
                                    try {
                                        const jsonStr = line.slice(6);
                                        // console.log('[SSE] 마지막 이벤트 파싱 시도:', jsonStr.substring(0, 150));
                                        const data = JSON.parse(jsonStr);
                                        // console.log('[SSE] 마지막 이벤트 파싱 성공 - type:', data.type);
                                        
                                        // 이벤트 타입별 처리 (위의 로직 재사용)
                                        // token 이벤트 처리
                                        if (data.type === 'token') {
                                            // console.log('[TOKEN] 마지막 버퍼에서 받음:', data.content.substring(0, 50) + '...');
                                            
                                            // 사용자 입력과 정확히 동일한 토큰만 건너뛰기
                                            const tokenContent = data.content.trim();
                                            if (tokenContent && tokenContent.toLowerCase() === userMessageNormalized && tokenContent.length === userMessageNormalized.length) {
                                                // console.log('[TOKEN] 사용자 입력과 정확히 동일한 토큰 감지 - 건너뜀:', tokenContent);
                                                continue;
                                            }
                                            
                                            // 부분 일치는 필터링하지 않음
                                            fullContent += data.content;
                                            hasReceivedToken = true;
                                            const formattedContent = formatMessage(fullContent);
                                            bubble.innerHTML = formattedContent + '<span class="streaming-cursor">▊</span>';
                                            messagesContainer.scrollTop = messagesContainer.scrollHeight;
                                        }
                                        // done 이벤트 처리
                                        else if (data.type === 'done') {
                                            // console.log('[DONE] 마지막 버퍼에서 받음:', { fullContent: fullContent.length, final_response: data.final_response?.length });
                                            doneReceived = true;
                                            let finalText = fullContent.trim() || data.final_response || '';
                                            if (finalText.trim()) {
                                                const formattedContent = formatMessage(finalText);
                                                bubble.innerHTML = formattedContent;  // streaming-cursor 제거
                                                messagesContainer.scrollTop = messagesContainer.scrollHeight;
                                            }
                                            sendBtn.disabled = false;
                                        }
                                    } catch (parseError) {
                                        // console.error('[SSE] 마지막 이벤트 파싱 오류:', parseError);
                                    }
                                }
                            }
                        }
                    }
                    // 버퍼에 남은 줄들도 처리 (완전하지 않은 이벤트)
                    if (buffer.trim()) {
                        const lines = buffer.split('\n');
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const jsonStr = line.slice(6);
                                    const data = JSON.parse(jsonStr);
                                    // console.log('[SSE] 남은 줄에서 이벤트 파싱:', data.type);
                                    // 위와 동일한 처리
                                    if (data.type === 'token') {
                                        // 사용자 입력과 정확히 동일한 토큰만 건너뛰기
                                        const tokenContent = data.content.trim();
                                        if (tokenContent && tokenContent.toLowerCase() === userMessageNormalized && tokenContent.length === userMessageNormalized.length) {
                                            continue;
                                        }
                                        
                                        // 부분 일치는 필터링하지 않음
                                        fullContent += data.content;
                                        hasReceivedToken = true;
                                        const formattedContent = formatMessage(fullContent);
                                        bubble.innerHTML = formattedContent + '<span class="streaming-cursor">▊</span>';
                                    } else if (data.type === 'done') {
                                        doneReceived = true;
                                        let finalText = fullContent.trim() || data.final_response || '';
                                        
                                        // 서버 프롬프트에서 이미 처리하므로 필터링 불필요
                                        // 최소한의 안전장치: 사용자 입력과 정확히 동일한 응답만 필터링
                                        if (userMessageNormalized && finalText.trim().toLowerCase() === userMessageNormalized) {
                                            // console.warn('[DONE] 사용자 입력과 정확히 동일한 응답 감지 - 건너뜀');
                                            finalText = '';
                                        }
                                        
                                        if (finalText.trim()) {
                                            const formattedContent = formatMessage(finalText);
                                            bubble.innerHTML = formattedContent;
                                        }
                                        sendBtn.disabled = false;
                                    }
                                } catch (parseError) {
                                    // console.error('[SSE] 남은 줄 파싱 오류:', parseError);
                                }
                            }
                        }
                    }
                }
                break;  // done이면 루프 종료
            }
        }
        
        // while 루프가 끝났지만 done 이벤트를 받지 못한 경우 처리
        // done 이벤트를 받았다면 이미 bubble.innerHTML이 업데이트되었으므로 여기서는 건너뜀
        if (!doneReceived) {
            // console.warn('[LOOP END] done 이벤트를 받지 못함 - fallback 처리');
            // console.log('[LOOP END] fullContent:', fullContent.length, 'finalResponseFromServer:', finalResponseFromServer.length);
            
            // fullContent 또는 finalResponseFromServer 사용
            let finalContent = fullContent.trim() || finalResponseFromServer.trim() || '';
            
            // 서버 프롬프트에서 이미 처리하므로 필터링 불필요
            // 최소한의 안전장치: 사용자 입력과 정확히 동일한 응답만 필터링
            if (userMessageNormalized && finalContent.trim().toLowerCase() === userMessageNormalized) {
                // console.warn('[LOOP END] 사용자 입력과 정확히 동일한 응답 감지 - 건너뜀');
                finalContent = '';
            }
            
            if (finalContent) {
                // console.log('[LOOP END] 최종 응답 표시 - fullContent 또는 finalResponseFromServer 사용');
                // JSON 메타데이터 제거
                jsonBlocks.forEach(jsonBlock => {
                    finalContent = finalContent.replace(jsonBlock.text, '').trim();
                });
                finalContent = finalContent.replace(/^\s*\{[\s\S]*?\}\s*\{[\s\S]*?\}\s*/g, '');
                finalContent = finalContent.replace(/^\s*\{[\s\S]*?\}\s*/g, '');
                
                const finalFormattedContent = formatMessage(finalContent);
                bubble.innerHTML = finalFormattedContent;  // streaming-cursor 제거
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            } else {
                // console.warn('[LOOP END] fullContent와 finalResponseFromServer 모두 없음');
                // 응답이 없어도 streaming-cursor 제거
                bubble.innerHTML = '<span style="color: var(--text-secondary);">응답을 생성하지 못했습니다.</span>';
            }
        } else {
            // console.log('[LOOP END] done 이벤트를 이미 받았음 - 건너뜀');
        }
        
        if (currentResponseNode === 'simple_chat_specialist' || currentResponseNode === 'transaction_specialist') {
            shouldShowThinkingProcess = false;
        } else {
            // nodeSearchInfo에 있는 노드들을 thinkingSteps에 추가 (아직 추가되지 않은 경우)
            const filteredNodeSearchInfo = Object.fromEntries(
                Object.entries(nodeSearchInfo).filter(([nodeName]) => 
                    nodeName !== 'simple_chat_specialist' && nodeName !== 'transaction_specialist'
                )
            );
            
            // nodeSearchInfo에 있지만 thinkingSteps에 없는 노드 추가
            Object.entries(filteredNodeSearchInfo).forEach(([nodeName, searchInfo]) => {
                const stepIndex = thinkingSteps.findIndex(step => {
                    const stepNodeName = getNodeNameFromStep(step.title);
                    return stepNodeName === nodeName;
                });
                
                if (stepIndex === -1) {
                    const stepTitle = getNodeStepTitle(nodeName, '');
                    if (stepTitle) {
                        const nodeDisplay = nodeHistory.find(n => n.name === nodeName)?.display || NODE_DISPLAY_NAMES[nodeName] || nodeName;
                        addOrUpdateThinkingStep(nodeName, nodeDisplay, searchInfo);
                    }
                } else {
                    // 이미 있는 경우 searchInfo 업데이트
                    const content = createThinkingStepContent(nodeName, '', searchInfo);
                    thinkingSteps[stepIndex].content = content || thinkingSteps[stepIndex].content;
                    thinkingSteps[stepIndex].queries = searchInfo.queries || thinkingSteps[stepIndex].queries;
                    thinkingSteps[stepIndex].searchInfo = searchInfo;
                }
            });
            
            if (thinkingSteps.length > 0 || Object.keys(filteredNodeSearchInfo).length > 0) {
                shouldShowThinkingProcess = true;
                
                if (!thinkingProcessUI && thinkingSteps.length > 0) {
                    thinkingProcessUI = createThinkingProcessUI(thinkingSteps);
                } else if (thinkingProcessUI) {
                    updateThinkingProcessUI();
                }
                
                if (thinkingProcessUI && !messageDiv.contains(thinkingProcessUI)) {
                    messageDiv.appendChild(thinkingProcessUI);
                }
                
                if (thinkingProcessUI) {
                    thinkingProcessUI.classList.add('collapsed');
                    thinkingProcessUI.classList.remove('expanded');
                }
            }
        }
        
        sendBtn.disabled = false;
        
    } catch (error) {
        if (error.name === 'AbortError') {
            // console.log('요청이 취소되었습니다.');
        } else {
            // console.error('스트리밍 오류:', error);
            bubble.innerHTML = formatMessage('연결 오류가 발생했습니다. 다시 시도해주세요.');
        }
        sendBtn.disabled = false;
    }
}

async function sendMessageNormal(message, sendBtn) {
    const loadingId = showLoading();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            }),
            signal: currentAbortController.signal
        });
        
        const data = await response.json();
        
        hideLoading(loadingId);
        sendBtn.disabled = false;
        
        if (data.error) {
            addMessageToChat('assistant', '죄송합니다. 오류가 발생했습니다: ' + data.error);
        } else {
            addMessageToChat('assistant', data.response);
        }
        
    } catch (error) {
        hideLoading(loadingId);
        sendBtn.disabled = false;
        if (error.name !== 'AbortError') {
            addMessageToChat('assistant', '연결 오류가 발생했습니다. 다시 시도해주세요.');
            // console.error('Error:', error);
        }
    }
}

function addMessageToChat(role, content, scroll = true) {
    const messagesContainer = document.getElementById('chatMessages');
    
    const emptyState = messagesContainer.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    const formattedContent = formatMessage(content);
    bubble.innerHTML = formattedContent;
    
    messageDiv.appendChild(bubble);
    messagesContainer.appendChild(messageDiv);
    
    if (scroll) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

function formatMessage(text) {
    if (!text) return '';
    
    // 코드 블록 먼저 처리
    const codeBlocks = [];
    let codeBlockIndex = 0;
    text = text.replace(/```([\s\S]*?)```/g, (match, code) => {
        const placeholder = `__CODE_BLOCK_${codeBlockIndex}__`;
        codeBlocks[codeBlockIndex] = code;
        codeBlockIndex++;
        return placeholder;
    });
    
    // 마크다운 이미지 처리 (![alt](url)) -> <img> 태그로 변환
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
        // URL 검증 및 이스케이프
        const safeUrl = url.trim();
        const safeAlt = alt.trim() || '이미지';
        // 이미지 태그 생성 (반응형 스타일 포함)
        return `<div class="faq-image-container"><img src="${safeUrl}" alt="${safeAlt}" class="faq-image" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';"><div class="faq-image-error" style="display:none;">이미지를 불러올 수 없습니다: <a href="${safeUrl}" target="_blank" rel="noopener noreferrer">링크</a></div></div>`;
    });
    
    // 번호 리스트 처리
    text = text.replace(/((?:^\s*\d+\.\s+.+?(?:\n|$))+)/gm, (match) => {
        const lines = match.split('\n');
        const items = [];
        
        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            
            const numberedMatch = trimmed.match(/^\d+\.\s+(.+)$/);
            if (numberedMatch) {
                items.push(numberedMatch[1]);
            }
        }
        
        if (items.length > 0) {
            return '<ol>' + items.map(item => `<li>${item}</li>`).join('') + '</ol>';
        }
        return match;
    });
    
    // 불릿 포인트 리스트 처리
    text = text.replace(/((?:^[-•]\s+.+$(?:\n|$))+)/gm, (match) => {
        const lines = match.trim().split('\n');
        const items = [];
        
        for (const line of lines) {
            const trimmed = line.trim();
            const bulletMatch = trimmed.match(/^[-•]\s+(.+)$/);
            if (bulletMatch) {
                items.push(bulletMatch[1]);
            }
        }
        
        if (items.length > 0) {
            return '<ul>' + items.map(item => `<li>${item}</li>`).join('') + '</ul>';
        }
        return match;
    });
    
    let html = text;
    
    // HTML 태그 보호
    const htmlPlaceholders = [];
    let placeholderIndex = 0;
    html = html.replace(/(<[^>]+>)/g, (match) => {
        const placeholder = `__HTML_TAG_${placeholderIndex}__`;
        htmlPlaceholders[placeholderIndex] = match;
        placeholderIndex++;
        return placeholder;
    });
    
    // HTML 이스케이프
    html = html
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    
    // 줄바꿈 처리
    html = html.replace(/\n/g, '<br>');
    
    // HTML 태그 복원
    htmlPlaceholders.forEach((tag, index) => {
        html = html.replace(`__HTML_TAG_${index}__`, tag);
    });
    
    // 코드 블록 복원
    codeBlocks.forEach((code, index) => {
        const escapedCode = code
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        html = html.replace(`__CODE_BLOCK_${index}__`, `<pre><code>${escapedCode}</code></pre>`);
    });
    
    // 인라인 코드 처리
    html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    
    // 강조 표시
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // 링크 변환
    html = html.replace(
        /(https?:\/\/[^\s<>\)]+)/g,
        (match) => {
            let fixedUrl = match
                .replace(/xn--com[^\/]*/gi, 'com')
                .replace(/\)[^\/]*/g, '');
            // .replace(/[^\/]$/, '') 제거 - 이 정규식이 URL의 마지막 문자를 잘라버림
            
            if (fixedUrl.includes('bithumb')) {
                if (fixedUrl.includes('support.bithumb')) {
                    fixedUrl = 'https://support.bithumb.com/hc/ko';
                } else if (fixedUrl.includes('www.bithumb') || fixedUrl.includes('bithumb.com')) {
                    fixedUrl = 'https://www.bithumb.com';
                }
            }
            
            return `<a href="${fixedUrl}" target="_blank" rel="noopener noreferrer">${fixedUrl}</a>`;
        }
    );
    
    // 연속된 <br>를 단락 구분으로 변환
    html = html.replace(/(<br>\s*){2,}(?![^<]*<\/[ou]l>)/g, '</p><p>');
    html = '<p>' + html + '</p>';
    html = html.replace(/<p>\s*<\/p>/g, '');
    html = html.replace(/<p>(<pre>)/g, '$1');
    html = html.replace(/(<\/pre>)<\/p>/g, '$1');
    html = html.replace(/<p>(<[ou]l>)/g, '$1');
    html = html.replace(/(<\/[ou]l>)<\/p>/g, '$1');
    
    return html;
}

function showLoading() {
    const messagesContainer = document.getElementById('chatMessages');
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message assistant';
    loadingDiv.id = 'loadingMessage';
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble loading';
    bubble.innerHTML = `
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
    `;
    
    loadingDiv.appendChild(bubble);
    messagesContainer.appendChild(loadingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return 'loadingMessage';
}

function hideLoading(loadingId) {
    const loading = document.getElementById(loadingId);
    if (loading) {
        loading.remove();
    }
}

async function clearChat() {
    if (!confirm('대화 기록을 모두 삭제하시겠습니까?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/chat/history/${sessionId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            const messagesContainer = document.getElementById('chatMessages');
            messagesContainer.innerHTML = `
                <div class="empty-state">
                    <h2>안녕하세요! 👋</h2>
                    <p>블록체인과 빗썸 거래소에 관련된 질문을 해주세요.</p>
                    <p style="margin-top: var(--space-md); font-size: var(--font-size-sm);">
                        트랜잭션 조회, FAQ 검색, 블록체인 정보 등 무엇이든 물어보세요.
                    </p>
                </div>
            `;
        }
    } catch (error) {
        // console.error('대화 기록 삭제 실패:', error);
        alert('대화 기록 삭제 중 오류가 발생했습니다.');
    }
}