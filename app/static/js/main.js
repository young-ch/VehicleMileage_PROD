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
