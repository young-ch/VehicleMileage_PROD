"""통계 라우트"""
from flask import render_template, jsonify
from flask_login import login_required
from sqlalchemy import func
from ..extensions import db
from ..models.personnel import Personnel, Department
from ..models.jira import JiraIssue
from ..models.user import User
from ..utils.decorators import permission_required
from . import stats_bp


@stats_bp.route('/')
@login_required
@permission_required('stats_view')
def dashboard():
    """통계 대시보드"""
    return render_template('stats/dashboard.html')


@stats_bp.route('/api/personnel')
@login_required
@permission_required('stats_view')
def personnel_stats():
    """인원 통계 API (부서 통계 제외, 상태 통계를 입사/퇴사로 분류)"""
    # 상태별 인원 (active/inactive만 분류)
    status_stats = db.session.query(
        Personnel.status,
        func.count(Personnel.id)
    ).filter(Personnel.status.in_(['active', 'inactive']))\
     .group_by(Personnel.status).all()
     
    status_labels = []
    status_data = []
    for s in status_stats:
        label = '입사(재직)' if s[0] == 'active' else '퇴사(퇴직)'
        status_labels.append(label)
        status_data.append(s[1])
    
    # 직급별 인원
    rank_stats = db.session.query(
        Personnel.rank,
        func.count(Personnel.id)
    ).filter(
        Personnel.status == 'active',
        Personnel.rank.isnot(None)
    ).group_by(Personnel.rank).all()
    
    return jsonify({
        'status': {
            'labels': status_labels,
            'data': status_data,
        },
        'rank': {
            'labels': [r[0] or '미설정' for r in rank_stats],
            'data': [r[1] for r in rank_stats],
        },
    })


@stats_bp.route('/api/jira')
@login_required
@permission_required('stats_view')
def jira_stats():
    """JIRA 이슈 통계 API"""
    # 상태별 이슈
    status_stats = db.session.query(
        JiraIssue.status,
        func.count(JiraIssue.id)
    ).group_by(JiraIssue.status).all()
    
    # 우선순위별 이슈
    priority_stats = db.session.query(
        JiraIssue.priority,
        func.count(JiraIssue.id)
    ).group_by(JiraIssue.priority).all()
    
    # 유형별 이슈
    type_stats = db.session.query(
        JiraIssue.issue_type,
        func.count(JiraIssue.id)
    ).group_by(JiraIssue.issue_type).all()
    
    # 담당자별 이슈 (상위 10명)
    assignee_stats = db.session.query(
        User.username,
        func.count(JiraIssue.id)
    ).join(User, JiraIssue.assignee_id == User.id
    ).group_by(User.username
    ).order_by(func.count(JiraIssue.id).desc()
    ).limit(10).all()
    
    # 월별 이슈 생성 추이 (최근 12개월)
    monthly_stats = db.session.query(
        func.strftime('%Y-%m', JiraIssue.created_date),
        func.count(JiraIssue.id)
    ).filter(
        JiraIssue.created_date.isnot(None)
    ).group_by(
        func.strftime('%Y-%m', JiraIssue.created_date)
    ).order_by(
        func.strftime('%Y-%m', JiraIssue.created_date)
    ).limit(12).all()
    
    return jsonify({
        'status': {
            'labels': [s[0] or '미설정' for s in status_stats],
            'data': [s[1] for s in status_stats],
        },
        'priority': {
            'labels': [p[0] or '미설정' for p in priority_stats],
            'data': [p[1] for p in priority_stats],
        },
        'type': {
            'labels': [t[0] or '미설정' for t in type_stats],
            'data': [t[1] for t in type_stats],
        },
        'assignee': {
            'labels': [a[0] for a in assignee_stats],
            'data': [a[1] for a in assignee_stats],
        },
        'monthly': {
            'labels': [m[0] for m in monthly_stats],
            'data': [m[1] for m in monthly_stats],
        },
    })
