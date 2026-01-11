/**
 * Google AdSense 광고 최적화 스크립트
 */

(function() {
    'use strict';

    // AdSense 광고 로드 상태 관리
    const adContainers = document.querySelectorAll('.adsense-container');
    
    // 광고 컨테이너 확인 및 표시 처리
    function checkAndShowAds(container) {
        // 실제 광고 코드(ins 태그)가 있으면 표시
        const hasAdCode = container.querySelector('ins.adsbygoogle');
        // 또는 주석이 아닌 실제 내용이 있는지 확인
        const hasContent = container.innerHTML.trim() !== '' && 
                          !container.innerHTML.includes('광고 코드를 여기에 삽입하세요');
        
        if (hasAdCode || hasContent) {
            container.classList.add('has-ads');
            container.style.display = 'flex';
        }
    }
    
    // 광고가 로드되면 placeholder 숨기기
    function handleAdLoad(container) {
        if (container.querySelector('ins')) {
            container.classList.add('loaded');
            checkAndShowAds(container);
        }
    }
    
    // 초기 로드 시 광고 확인
    adContainers.forEach(container => {
        checkAndShowAds(container);
    });

    // Intersection Observer로 광고 로드 최적화
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const container = entry.target;
                    handleAdLoad(container);
                    
                    // 광고 스크립트가 로드되지 않았다면 로드
                    if (!window.adsbygoogle) {
                        const script = document.createElement('script');
                        script.async = true;
                        script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5240424281235281';
                        script.crossOrigin = 'anonymous';
                        document.head.appendChild(script);
                    }
                    
                    // AdSense 광고 푸시 (이미 삽입된 경우)
                    if (container.querySelector('ins.adsbygoogle')) {
                        try {
                            (adsbygoogle = window.adsbygoogle || []).push({});
                        } catch (e) {
                            console.error('AdSense push error:', e);
                        }
                    }
                    
                    observer.unobserve(container);
                }
            });
        }, {
            rootMargin: '50px' // 50px 전에 미리 로드
        });

        adContainers.forEach(container => {
            observer.observe(container);
        });
    }

    // 광고 클릭 추적 (선택사항)
    document.addEventListener('click', function(e) {
        const adLink = e.target.closest('.adsbygoogle, .adsense-container a');
        if (adLink) {
            // 광고 클릭 이벤트 추적 (GA4 등)
            if (typeof gtag !== 'undefined') {
                gtag('event', 'ad_click', {
                    'event_category': 'AdSense',
                    'event_label': adLink.closest('.adsense-container')?.className || 'unknown'
                });
            }
        }
    });

    // 페이지 로드 후 모든 광고 푸시
    window.addEventListener('load', function() {
        if (window.adsbygoogle) {
            adContainers.forEach(container => {
                const ads = container.querySelectorAll('ins.adsbygoogle');
                ads.forEach(ad => {
                    try {
                        (adsbygoogle = window.adsbygoogle || []).push({});
                    } catch (e) {
                        console.error('AdSense push error:', e);
                    }
                });
            });
        }
    });
})();
