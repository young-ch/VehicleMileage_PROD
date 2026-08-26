/**
 * SMU JIRA 관리 시스템 - Main JavaScript
 */

// ---- Mobile sidebar toggle ----
document.addEventListener('DOMContentLoaded', function() {
    const menuBtn = document.querySelector('.mobile-menu-btn');
    const sidebar = document.querySelector('.sidebar');
    
    if (menuBtn && sidebar) {
        menuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
    
    // Auto-dismiss flash messages after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});


/**
 * 텍스트 붙여넣기 파싱 결과를 저장 API 호출
 */
function saveParsedData(endpoint, rows) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content
        || document.querySelector('input[name="csrf_token"]')?.value;
    
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ rows: rows }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            // 2초 후 목록 페이지로 이동
            setTimeout(() => {
                const currentPath = window.location.pathname;
                window.location.href = currentPath.replace('/paste', '');
            }, 2000);
        } else {
            showToast(data.message || '저장 실패', 'danger');
        }
        
        // 에러 표시
        if (data.errors && data.errors.length > 0) {
            const errorContainer = document.getElementById('save-errors');
            if (errorContainer) {
                errorContainer.innerHTML = data.errors.map(e => 
                    `<div class="alert alert-danger">⚠️ ${e.line}행: ${e.message}</div>`
                ).join('');
            }
        }
    })
    .catch(error => {
        showToast('네트워크 오류: ' + error.message, 'danger');
    });
}


/**
 * 미리보기 테이블에서 데이터를 추출
 */
function getPreviewData() {
    const table = document.getElementById('preview-table');
    if (!table) return [];
    
    const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.dataset.field);
    const rows = [];
    
    table.querySelectorAll('tbody tr').forEach(tr => {
        const row = {};
        tr.querySelectorAll('td').forEach((td, idx) => {
            if (headers[idx]) {
                const input = td.querySelector('input, select');
                row[headers[idx]] = input ? input.value : td.textContent.trim();
            }
        });
        rows.push(row);
    });
    
    return rows;
}


/**
 * Toast 알림 표시
 */
function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    const icons = {
        success: '✅',
        danger: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    const toast = document.createElement('div');
    toast.className = `toast alert alert-${type}`;
    toast.innerHTML = `${icons[type] || ''} ${message}`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}


/**
 * Confirm 다이얼로그
 */
function confirmAction(message) {
    return confirm(message);
}


// ---- 날짜 복사 붙여넣기 (Paste) 자동 파싱 정규화 헬퍼 ----
document.addEventListener('paste', function(e) {
    // 포커스된 요소가 날짜(type="date") 입력창인 경우에만 작동
    const target = e.target;
    if (target && target.tagName === 'INPUT' && target.type === 'date') {
        // 붙여넣기된 클립보드 텍스트 획득
        const pastedText = (e.clipboardData || window.clipboardData).getData('text');
        if (!pastedText) return;
        
        let cleaned = pastedText.trim();
        // 끝의 온점 제거 (예: "2026. 8. 18." -> "2026. 8. 18")
        if (cleaned.endsWith('.')) {
            cleaned = cleaned.slice(0, -1);
        }
        
        let targetDate = null;
        
        // 1) 8자리 숫자 판별 (예: 20260818)
        if (/^\d{8}$/.test(cleaned)) {
            targetDate = `${cleaned.slice(0, 4)}-${cleaned.slice(4, 6)}-${cleaned.slice(6, 8)}`;
        } else {
            // 2) 온점(.), 대시(-), 슬래시(/), 공백 등으로 구성된 경우 분리하여 매칭
            const parts = cleaned.split(/[\.\-\/\s,]+/);
            if (parts.length === 3) {
                let year = parts[0].trim();
                let month = parts[1].trim();
                let day = parts[2].trim();
                
                // 년도가 4자리인 경우 (예: 2026. 8. 18)
                if (year.length === 4) {
                    month = month.padStart(2, '0');
                    day = day.padStart(2, '0');
                    targetDate = `${year}-${month}-${day}`;
                } 
                // 년도가 맨 뒤에 배치된 경우 (예: 18/08/2026)
                else if (day.length === 4) {
                    const tempYear = day;
                    month = month.padStart(2, '0');
                    const tempDay = year.padStart(2, '0');
                    targetDate = `${tempYear}-${month}-${tempDay}`;
                }
            }
        }
        
        // 올바른 날짜 포맷이 추출되었다면 기본 동작을 막고 꽂아줌
        if (targetDate && /^\d{4}-\d{2}-\d{2}$/.test(targetDate)) {
            e.preventDefault();
            target.value = targetDate;
            
            // 변경 이벤트 강제 트리거 (프레임워크 연동을 위해)
            const event = new Event('change', { bubbles: true });
            target.dispatchEvent(event);
        }
    }
});
