// Explorer JavaScript - Extracted from explorer_ui.html
function appData() {
    return {
        supportedChains: [],
        externalChains: [],
        isLoading: false,
        isLoadingChains: true,
        error: null,
        init() {
            this.fetchSupportedChains();
            this.externalChains = [
                {name: 'Henesys', explorer: 'https://subnets.avax.network/henesys'},
                {name: 'Paycoin', explorer: 'https://scan.payprotocol.io/'},
                {name: 'Vaulta', explorer: 'https://unicove.com/ko/vaulta'},
                {name: 'POKTscan', explorer: 'https://poktscan.com/'}
            ];
        },
        async fetchSupportedChains() {
            this.isLoadingChains = true;
            try {
                const res = await fetch('/api/chains');
                const data = await res.json();
                this.supportedChains = data.supportedChains || [];
            } catch (err) {
                console.error("지원 체인 정보를 불러오는 데 실패했습니다:", err);
                this.error = "지원 체인 정보를 불러오는 중 오류가 발생했습니다.";
            } finally {
                this.isLoadingChains = false;
            }
        },
        async lookupTx() {
            const txid = document.getElementById("txid").value.trim().replace(/ /g, '');
            const resultDiv = document.getElementById("result");
            
            if (!txid) {
                resultDiv.innerHTML = `
                    <div class="error-message">
                        트랜잭션 해시를 입력해주세요.
                    </div>
                `;
                resultDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
                return;
            }

            this.isLoading = true;
            resultDiv.innerHTML = '<div class="loading">트랜잭션을 조회하는 중입니다...</div>';
            resultDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });

            try {
                const res = await fetch(`/api/tx/${txid}`);
                
                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
                }
                
                const data = await res.json();
                
                // 디버깅: API 응답 확인
                console.log('API 응답:', data);

                if (!data.found || !data.results || data.results.length === 0) {
                    resultDiv.innerHTML = `
                        <div class="error-message">
                            체인에서 해당 트랜잭션을 찾을 수 없습니다. 트랜잭션 해시를 확인해주세요.
                            ${data.message ? `<br><small>${data.message}</small>` : ''}
                        </div>
                    `;
                    // 결과가 없을 때는 광고 숨김
                    const adsenseBelow = document.getElementById('adsense-below-results');
                    if (adsenseBelow) {
                        adsenseBelow.style.display = 'none';
                    }
                    return;
                }

                // 결과가 있을 때 광고 표시
                const adsenseBelow = document.getElementById('adsense-below-results');
                if (adsenseBelow) {
                    adsenseBelow.style.display = 'flex';
                    // 스크롤하여 광고가 보이도록
                    setTimeout(() => {
                        adsenseBelow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }, 300);
                }

                // 결과 렌더링
                const resultsHTML = data.results.map(tx => {
                    // 디버깅: 각 트랜잭션 데이터 확인
                    console.log('트랜잭션 데이터:', tx);
                    
                    // 데이터 검증
                    if (!tx || !tx.txid) {
                        console.error('유효하지 않은 트랜잭션 데이터:', tx);
                        return '';
                    }
                    
                    // 안전한 문자열 이스케이프 (XSS 방지)
                    const escapeHtml = (str) => {
                        if (str == null) return '';
                        return String(str)
                            .replace(/&/g, '&amp;')
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;')
                            .replace(/"/g, '&quot;')
                            .replace(/'/g, '&#039;');
                    };
                    
                    const safeTxid = escapeHtml(tx.txid);
                    const safeFrom = tx.from ? escapeHtml(tx.from) : '';
                    const safeTo = tx.to ? escapeHtml(tx.to) : '';
                    const safeValue = tx.value != null ? escapeHtml(String(tx.value)) : '';
                    const safeBlockNumber = tx.blockNumber != null ? escapeHtml(String(tx.blockNumber)) : '';
                    const safeSymbol = escapeHtml(tx.symbol || tx.chain || 'Unknown');
                    const safeExplorer = escapeHtml(tx.explorer || '');
                    const safeStatus = tx.status ? escapeHtml(tx.status.toLowerCase()) : '';
                    const statusText = tx.status === 'confirmed' ? '✓ 확인됨' : 
                                     tx.status === 'failed' ? '✕ 실패' : 
                                     tx.status === 'pending' ? '⏳ 대기중' : escapeHtml(tx.status || '');
                    
                    return `
                    <div class="transaction-card fade-in">
                        <div class="transaction-header">
                            <div class="transaction-chain">
                                <span class="chain-badge">${safeSymbol}</span>
                                ${tx.status ? `
                                    <span class="transaction-status status-${safeStatus}">
                                        ${statusText}
                                    </span>
                                ` : ''}
                            </div>
                            <a href="${safeExplorer}${safeTxid}" target="_blank" rel="noopener noreferrer" class="transaction-link">
                                <span>탐색기에서 보기</span>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                                    <polyline points="15 3 21 3 21 9"></polyline>
                                    <line x1="10" y1="14" x2="21" y2="3"></line>
                                </svg>
                            </a>
                        </div>

                        <div class="info-grid">
                            <div class="info-item">
                                <span class="info-label">트랜잭션 ID</span>
                                <div class="info-value">
                                    ${safeTxid}
                                    <button class="copy-button btn btn-sm" onclick="copyToClipboard('${safeTxid.replace(/'/g, "\\'")}', event)">복사</button>
                                </div>
                            </div>

                            ${tx.from ? `
                                <div class="info-item">
                                    <span class="info-label">보낸 주소</span>
                                    <div class="info-value">
                                        ${safeFrom}
                                        <button class="copy-button btn btn-sm" onclick="copyToClipboard('${safeFrom.replace(/'/g, "\\'")}', event)">복사</button>
                                    </div>
                                </div>
                            ` : ''}

                            ${tx.to ? `
                                <div class="info-item">
                                    <span class="info-label">받는 주소</span>
                                    <div class="info-value">
                                        ${safeTo}
                                        <button class="copy-button btn btn-sm" onclick="copyToClipboard('${safeTo.replace(/'/g, "\\'")}', event)">복사</button>
                                    </div>
                                </div>
                            ` : ''}

                            ${tx.value != null ? `
                                <div class="info-item">
                                    <span class="info-label">금액</span>
                                    <div class="info-value">${safeValue}</div>
                                </div>
                            ` : ''}

                            ${tx.blockNumber != null ? `
                                <div class="info-item">
                                    <span class="info-label">블록 번호</span>
                                    <div class="info-value">${safeBlockNumber}</div>
                                </div>
                            ` : ''}

                            ${tx.destination_tag != null ? `
                                <div class="info-item">
                                    <span class="info-label">Destination Tag</span>
                                    <div class="info-value">
                                        ${escapeHtml(String(tx.destination_tag))}
                                        <button class="copy-button btn btn-sm" onclick="copyToClipboard('${escapeHtml(String(tx.destination_tag)).replace(/'/g, "\\'")}', event)">복사</button>
                                    </div>
                                </div>
                            ` : ''}
                        </div>

                        ${tx.note ? `
                            <div class="transaction-note">
                                ${escapeHtml(tx.note)}
                            </div>
                        ` : ''}
                    </div>
                `;
                }).filter(html => html !== '').join(''); // 빈 문자열 제거
                
                if (!resultsHTML || resultsHTML.trim() === '') {
                    console.error('결과 HTML이 비어있습니다.');
                    resultDiv.innerHTML = `
                        <div class="error-message">
                            결과를 렌더링할 수 없습니다. 콘솔을 확인해주세요.
                        </div>
                    `;
                    return;
                }
                
                console.log('렌더링할 HTML 길이:', resultsHTML.length);
                console.log('resultDiv 요소:', resultDiv);
                console.log('resultDiv 현재 내용 길이:', resultDiv.innerHTML.length);
                
                // 기존 내용 클리어
                resultDiv.innerHTML = '';
                
                // HTML 삽입 (템플릿을 사용하여 안전하게)
                try {
                    resultDiv.innerHTML = resultsHTML;
                    
                    // fade-in 애니메이션 활성화 (fade-in-visible 클래스 추가)
                    // requestAnimationFrame을 사용하여 DOM 업데이트 후 클래스 추가
                    requestAnimationFrame(() => {
                        const transactionCards = resultDiv.querySelectorAll('.transaction-card.fade-in');
                        transactionCards.forEach((card, index) => {
                            // 각 카드를 순차적으로 표시
                            setTimeout(() => {
                                card.classList.add('fade-in-visible');
                            }, index * 50); // 50ms 간격으로 순차 표시
                        });
                    });
                    
                    // 삽입 후 확인
                    console.log('삽입 후 resultDiv 내용 길이:', resultDiv.innerHTML.length);
                    console.log('삽입 후 resultDiv 자식 요소 개수:', resultDiv.children.length);
                    
                    if (resultDiv.children.length === 0) {
                        console.error('경고: HTML이 삽입되었지만 자식 요소가 없습니다.');
                        console.error('삽입된 HTML (처음 500자):', resultsHTML.substring(0, 500));
                    }
                    
                    const computedStyle = window.getComputedStyle(resultDiv);
                    console.log('삽입 후 resultDiv 표시 상태:', {
                        display: computedStyle.display,
                        visibility: computedStyle.visibility,
                        opacity: computedStyle.opacity,
                        height: computedStyle.height,
                        offsetHeight: resultDiv.offsetHeight,
                        scrollHeight: resultDiv.scrollHeight
                    });
                    
                    // 첫 번째 자식 요소 확인
                    if (resultDiv.firstElementChild) {
                        const firstChild = resultDiv.firstElementChild;
                        const firstChildStyle = window.getComputedStyle(firstChild);
                        console.log('첫 번째 자식 요소:', {
                            tagName: firstChild.tagName,
                            className: firstChild.className,
                            display: firstChildStyle.display,
                            opacity: firstChildStyle.opacity,
                            visibility: firstChildStyle.visibility,
                            height: firstChild.offsetHeight
                        });
                    }
                    
                } catch (e) {
                    console.error('HTML 삽입 중 오류:', e);
                    resultDiv.innerHTML = `
                        <div class="error-message">
                            결과를 표시하는 중 오류가 발생했습니다: ${e.message}
                        </div>
                    `;
                    return;
                }
                
                // 결과 영역으로 스크롤
                setTimeout(() => {
                    resultDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            } catch (error) {
                console.error("조회 중 오류 발생:", error);
                resultDiv.innerHTML = `
                    <div class="error-message">
                        오류가 발생했습니다. 다시 시도해주세요.
                        <br><small>${error.message || '알 수 없는 오류'}</small>
                    </div>
                `;
                // 결과가 없을 때는 광고 숨김
                const adsenseBelow = document.getElementById('adsense-below-results');
                if (adsenseBelow) {
                    adsenseBelow.style.display = 'none';
                }
            } finally {
                this.isLoading = false;
            }
        },
        base64ToHex() {
            const base64Input = document.getElementById("base64-input").value.trim();
            const outputArea = document.getElementById("converter-output");
            
            if (!base64Input) {
                outputArea.innerHTML = `
                    <div class="error-message">
                        Base64 문자열을 입력해주세요.
                    </div>
                `;
                return;
            }

            try {
                const binaryString = atob(base64Input);
                let hexString = "";

                for (let i = 0; i < binaryString.length; i++) {
                    const byte = binaryString.charCodeAt(i);
                    const hexByte = byte.toString(16).padStart(2, '0');
                    hexString += hexByte;
                }
                
                const hexResult = hexString.toUpperCase();

                outputArea.innerHTML = `
                    <div class="result-item fade-in">
                        <span class="result-label">입력 Base64</span>
                        <div class="result-value">
                            ${base64Input}
                            <button class="copy-button btn btn-sm" onclick="copyToClipboard('${base64Input}', event)">복사</button>
                        </div>
                    </div>
                    <div class="result-item fade-in">
                        <span class="result-label">HEX 결과</span>
                        <div class="result-value">
                            ${hexResult}
                            <button class="copy-button btn btn-sm" onclick="copyToClipboard('${hexResult}', event)">복사</button>
                        </div>
                    </div>
                `;
            } catch (e) {
                outputArea.innerHTML = `
                    <div class="error-message">
                        유효하지 않은 Base64 문자열입니다.
                        <br><small>${e.message || '디코딩 오류'}</small>
                    </div>
                `;
                console.error("Base64 디코딩 오류:", e);
            }
        }
    };
}

async function copyToClipboard(text, event) {
    let success = false;
    try {
        await navigator.clipboard.writeText(text);
        success = true;
    } catch (err) {
        console.warn('Async Clipboard API not available, falling back to execCommand:', err);
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy');
            success = true;
        } catch (execErr) {
            console.error('클립보드 복사 실패:', execErr);
            alert("클립보드 복사에 실패했습니다.");
        } finally {
            document.body.removeChild(textArea);
        }
    }

    if (success) {
        const button = event.target.closest('button');
        if (button) {
            const originalText = button.textContent;
            button.classList.add('copied');
            button.textContent = '✓ 복사됨';
            setTimeout(() => {
                button.classList.remove('copied');
                button.textContent = originalText;
            }, 2000);
        }
    }
}
