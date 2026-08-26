"""통계 라우트"""
from flask import render_template, jsonify
from flask_login import login_required
from sqlalchemy import func
from ..extensions import db
from ..models.personnel import Personnel, Department
from ..models.jira import JiraIssue
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
    """인원 통계 API"""
    # 부서별 인원
    dept_stats = db.session.query(
        Department.name,
        func.count(Personnel.id)
    ).outerjoin(Personnel, db.and_(
        Personnel.department_id == Department.id,
        Personnel.status == 'active'
    )).group_by(Department.name).all()
    
    # 상태별 인원
    status_stats = db.session.query(
        Personnel.status,
        func.count(Personnel.id)
    ).group_by(Personnel.status).all()
    
    # 직급별 인원
    rank_stats = db.session.query(
        Personnel.rank,
        func.count(Personnel.id)
    ).filter(
        Personnel.status == 'active',
        Personnel.rank.isnot(None)
    ).group_by(Personnel.rank).all()
    
    return jsonify({
        'department': {
            'labels': [d[0] for d in dept_stats],
            'data': [d[1] for d in dept_stats],
        },
        'status': {
            'labels': [s[0] or '미설정' for s in status_stats],
            'data': [s[1] for s in status_stats],
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
    from ..models.personnel import Personnel
    assignee_stats = db.session.query(
        Personnel.name,
        func.count(JiraIssue.id)
    ).join(Personnel, JiraIssue.assignee_id == Personnel.id
    ).group_by(Personnel.name
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
