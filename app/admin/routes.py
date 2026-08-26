"""관리자 라우트 - 사용자 관리, 역할 관리"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from ..extensions import db
from ..models.user import User, Role
from ..utils.decorators import role_required
from ..utils.helpers import log_audit
from . import admin_bp


@admin_bp.route('/users')
@login_required
@role_required('admin')
def users():
    """사용자 목록"""
    page = request.args.get('page', 1, type=int)
    users_list = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    roles = Role.query.all()
    return render_template('admin/users.html', users=users_list, roles=roles)


@admin_bp.route('/users/<int:id>/role', methods=['POST'])
@login_required
@role_required('admin')
def change_role(id):
    """사용자 역할 변경"""
    user = User.query.get_or_404(id)
    new_role_id = request.form.get('role_id', type=int)
    
    if new_role_id:
        old_role = user.role.name
        user.role_id = new_role_id
        new_role = Role.query.get(new_role_id)
        
        log_audit('UPDATE', 'users', user.id,
                  old_values={'role': old_role},
                  new_values={'role': new_role.name})
        db.session.commit()
        
        flash(f'{user.username}의 역할이 {new_role.name}(으)로 변경되었습니다.', 'success')
    
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def toggle_active(id):
    """사용자 활성/비활성 토글"""
    user = User.query.get_or_404(id)
    user.is_active = not user.is_active
    
    log_audit('UPDATE', 'users', user.id,
              new_values={'is_active': user.is_active})
    db.session.commit()
    
    status = '활성화' if user.is_active else '비활성화'
    flash(f'{user.username} 계정이 {status}되었습니다.', 'info')
    return redirect(url_for('admin.users'))


@admin_bp.route('/audit')
@login_required
@role_required('admin')
def audit_logs():
    """감사 로그 조회"""
    from ..models.audit import AuditLog
    
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', '')
    
    query = AuditLog.query
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    
    logs = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=30, error_out=False
    )
    
    return render_template('admin/audit.html', logs=logs, action_filter=action_filter)
