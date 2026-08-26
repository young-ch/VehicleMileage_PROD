"""인증 라우트 - 로그인, 회원가입, 로그아웃"""
from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db
from ..models.user import User, Role
from ..utils.helpers import log_audit
from . import auth_bp
from .forms import LoginForm, RegisterForm


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """로그인"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('비활성화된 계정입니다. 관리자에게 문의하세요.', 'danger')
                return render_template('auth/login.html', form=form)
            
            login_user(user, remember=form.remember_me.data)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            
            flash(f'{user.username}님, 환영합니다!', 'success')
            
            # 이전 페이지로 리다이렉트
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('사용자명 또는 비밀번호가 올바르지 않습니다.', 'danger')
    
    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """회원가입"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        # 기본 역할: viewer
        viewer_role = Role.query.filter_by(name='viewer').first()
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            role_id=viewer_role.id,
            is_active=True,
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        log_audit('CREATE', 'users', user.id, new_values={
            'username': user.username,
            'email': user.email,
            'role': 'viewer',
        })
        db.session.commit()
        
        flash('회원가입이 완료되었습니다. 로그인해주세요.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """로그아웃"""
    logout_user()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('auth.login'))
