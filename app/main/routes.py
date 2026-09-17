"""메인 라우트 - 대시보드"""
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models.personnel import Personnel
from ..models.jira import JiraIssue
from ..models.audit import AuditLog
from . import main_bp


@main_bp.route('/')
def index():
    """루트 → 대시보드 또는 로그인으로 리다이렉트"""
    if current_user.is_authenticated:
        if current_user.is_viewer:
            return redirect(url_for('vehicle.index'))
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """메인 대시보드 (일반 사용자는 본인 관련 활동 및 이슈만 노출, 관리자는 전체 노출)"""
    if current_user.is_viewer:
        flash('대시보드 접근 권한이 없습니다.', 'warning')
        return redirect(url_for('vehicle.index'))
    from ..extensions import db
    
    # 일반 사용자용 JIRA 이슈 쿼리 필터링 정의
    jira_query = JiraIssue.query
    if not current_user.is_admin:
        jira_query = jira_query.filter(
            db.or_(
                JiraIssue.assignee_id == current_user.id,
                db.and_(
                    JiraIssue.assignee_id.is_(None),
                    JiraIssue.registered_by == current_user.id
                )
            )
        )
        
    # 요약 카드 데이터
    stats = {
        'total_personnel': Personnel.query.filter_by(status='active').count(),
        'total_issues': jira_query.count(),
        'open_issues': jira_query.filter(
            JiraIssue.status.in_(['Open', 'In Progress', 'To Do', 'open', 'in_progress', '시작전', '진행', '보류'])
        ).count(),
        'resolved_issues': jira_query.filter(
            JiraIssue.status.in_(['Resolved', 'Closed', 'Done', 'resolved', 'closed', 'done', '완료'])
        ).count(),
    }
    
    # 최근 활동 (감사 로그) - 관리자가 아니면 본인이 수행한 로그만 노출
    log_query = AuditLog.query
    if not current_user.is_admin:
        log_query = log_query.filter_by(user_id=current_user.id)
        
    recent_logs = log_query.order_by(
        AuditLog.created_at.desc()
    ).limit(10).all()
    
    # 최근 등록된 JIRA 이슈
    recent_issues = jira_query.order_by(
        JiraIssue.created_at.desc()
    ).limit(5).all()
    
    return render_template('main/dashboard.html',
                           stats=stats,
                           recent_logs=recent_logs,
                           recent_issues=recent_issues)
