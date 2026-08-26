"""권한 체크 데코레이터"""
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def role_required(*role_names):
    """특정 역할만 접근 허용하는 데코레이터
    
    사용 예:
        @role_required('admin')
        @role_required('admin', 'manager')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('로그인이 필요합니다.', 'warning')
                return redirect(url_for('auth.login'))
            if current_user.role.name not in role_names:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def permission_required(permission):
    """특정 권한만 접근 허용하는 데코레이터
    
    사용 예:
        @permission_required('personnel_create')
        @permission_required('jira_delete')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('로그인이 필요합니다.', 'warning')
                return redirect(url_for('auth.login'))
            if not current_user.has_permission(permission):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
