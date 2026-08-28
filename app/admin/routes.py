"""관리자 라우트 - 사용자 관리, 역할 관리"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models.user import User, Role
from ..utils.decorators import role_required
from ..utils.helpers import log_audit
from ..auth.forms import AdminUserCreateForm
from . import admin_bp


@admin_bp.route('/users')
@login_required
@role_required('admin')
def users():
    """사용자 목록"""
    page = request.args.get('page', 1, type=int)
    users_list = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
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
def audit_logs():
    """감사 로그 조회 (최고 관리자 및 차량 관리자 전용)"""
    if not (current_user.is_admin or current_user.is_vehicle_manager or current_user.has_permission('vehicle_manage')):
        flash('관리자 또는 차량관리자 권한이 필요합니다.', 'danger')
        return redirect(url_for('main.dashboard'))
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


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_user():
    """관리자용 사용자 생성"""
    form = AdminUserCreateForm()
    # 역할 리스트를 SelectField 초이스로 제공
    form.role_id.choices = [
        (r.id, r.name) for r in Role.query.all()
    ]
    
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip(),
            role_id=form.role_id.data,
            is_active=True
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        role_name = Role.query.get(form.role_id.data).name
        log_audit('CREATE', 'users', user.id, new_values={
            'username': user.username,
            'email': user.email,
            'role': role_name
        })
        db.session.commit()
        
        flash(f'새 사용자 계정 {user.username}이(가) 등록되었습니다.', 'success')
        return redirect(url_for('admin.users'))
        
    return render_template('admin/user_create.html', form=form)


@admin_bp.route('/users/<int:id>/reset-password', methods=['POST'])
@login_required
@role_required('admin')
def reset_password(id):
    """관리자용 타 사용자 비밀번호 강제 변경"""
    user = User.query.get_or_404(id)
    new_pwd = request.form.get('new_password', '').strip()
    
    if not new_pwd or len(new_pwd) < 8:
        return jsonify({'success': False, 'message': '비밀번호는 최소 8자 이상이어야 합니다.'}), 400
        
    user.set_password(new_pwd)
    log_audit('UPDATE', 'users', user.id, new_values={'admin_reset_password': True})
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'{user.username} 계정의 비밀번호가 성공적으로 재설정되었습니다.'})
