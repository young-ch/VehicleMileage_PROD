"""공통 헬퍼 함수"""
from flask import request
from flask_login import current_user
from ..extensions import db
from ..models.audit import AuditLog


def log_audit(action, target_table, target_id, old_values=None, new_values=None):
    """감사 로그 기록
    
    Args:
        action: 'CREATE', 'UPDATE', 'DELETE'
        target_table: 대상 테이블명
        target_id: 대상 레코드 ID
        old_values: 변경 전 값 (dict)
        new_values: 변경 후 값 (dict)
    """
    log = AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        target_table=target_table,
        target_id=target_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    # 별도 커밋은 하지 않음 - 호출자가 커밋


def parse_date(date_str):
    """다양한 날짜 형식 파싱"""
    if not date_str or date_str.strip() == '':
        return None
    
    from datetime import datetime
    formats = [
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%Y.%m.%d',
        '%d/%m/%Y',
        '%m/%d/%Y',
    ]
    
    date_str = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None
