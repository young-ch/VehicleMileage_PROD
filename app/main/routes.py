"""메인 라우트 - 대시보드"""
from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from ..models.personnel import Personnel
from ..models.jira import JiraIssue
from ..models.audit import AuditLog
from . import main_bp


@main_bp.route('/')
def index():
    """루트 → 대시보드 또는 로그인으로 리다이렉트"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """메인 대시보드"""
    # 요약 카드 데이터
    stats = {
        'total_personnel': Personnel.query.filter_by(status='active').count(),
        'total_issues': JiraIssue.query.count(),
        'open_issues': JiraIssue.query.filter(
            JiraIssue.status.in_(['Open', 'In Progress', 'To Do', 'open', 'in_progress'])
        ).count(),
        'resolved_issues': JiraIssue.query.filter(
            JiraIssue.status.in_(['Resolved', 'Closed', 'Done', 'resolved', 'closed', 'done'])
        ).count(),
    }
    
    # 최근 활동 (감사 로그)
    recent_logs = AuditLog.query.order_by(
        AuditLog.created_at.desc()
    ).limit(10).all()
    
    # 최근 등록된 JIRA 이슈
    recent_issues = JiraIssue.query.order_by(
        JiraIssue.created_at.desc()
    ).limit(5).all()
    
    return render_template('main/dashboard.html',
                           stats=stats,
                           recent_logs=recent_logs,
                           recent_issues=recent_issues)
