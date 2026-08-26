"""JIRA 이슈 관리 라우트"""
import json
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models.jira import JiraIssue, IssueComment
from ..models.personnel import Personnel
from ..models.audit import PasteHistory
from ..utils.decorators import permission_required
from ..utils.helpers import log_audit, parse_date
from . import jira_bp
from .forms import JiraIssueForm, JiraPasteForm
from .parser import parse_jira_text


@jira_bp.route('/')
@login_required
def list_issues():
    """이슈 목록"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    type_filter = request.args.get('type', '')
    
    query = JiraIssue.query
    
    if search:
        query = query.filter(
            db.or_(
                JiraIssue.jira_key.contains(search),
                JiraIssue.summary.contains(search),
                JiraIssue.reporter.contains(search),
            )
        )
    if status_filter:
        query = query.filter(JiraIssue.status == status_filter)
    if priority_filter:
        query = query.filter(JiraIssue.priority == priority_filter)
    if type_filter:
        query = query.filter(JiraIssue.issue_type == type_filter)
    
    pagination = query.order_by(JiraIssue.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('jira/list.html',
                           issues=pagination.items,
                           pagination=pagination,
                           search=search,
                           status_filter=status_filter,
                           priority_filter=priority_filter,
                           type_filter=type_filter)


@jira_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('jira_create')
def create():
    """이슈 개별 등록"""
    form = JiraIssueForm()
    form.assignee_id.choices = [(0, '선택하세요')] + [
        (p.id, f'{p.name} ({p.employee_id})') 
        for p in Personnel.query.filter_by(status='active').all()
    ]
    
    if form.validate_on_submit():
        issue = JiraIssue(
            jira_key=form.jira_key.data,
            summary=form.summary.data,
            description=form.description.data,
            issue_type=form.issue_type.data,
            priority=form.priority.data,
            status=form.status.data,
            assignee_id=form.assignee_id.data if form.assignee_id.data != 0 else None,
            reporter=form.reporter.data,
            created_date=form.created_date.data,
            resolved_date=form.resolved_date.data,
            due_date=form.due_date.data,
            sprint=form.sprint.data,
            epic=form.epic.data,
            labels=form.labels.data,
            registered_by=current_user.id,
        )
        db.session.add(issue)
        db.session.flush()
        
        log_audit('CREATE', 'jira_issues', issue.id, new_values=issue.to_dict())
        db.session.commit()
        
        flash(f'{issue.jira_key} 이슈가 등록되었습니다.', 'success')
        return redirect(url_for('jira.list_issues'))
    
    return render_template('jira/detail.html', form=form, mode='create')


@jira_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('jira_edit')
def edit(id):
    """이슈 수정"""
    issue = JiraIssue.query.get_or_404(id)
    form = JiraIssueForm(obj=issue)
    form.assignee_id.choices = [(0, '선택하세요')] + [
        (p.id, f'{p.name} ({p.employee_id})')
        for p in Personnel.query.filter_by(status='active').all()
    ]
    
    if form.validate_on_submit():
        old_values = issue.to_dict()
        
        form.populate_obj(issue)
        if form.assignee_id.data == 0:
            issue.assignee_id = None
        
        log_audit('UPDATE', 'jira_issues', issue.id,
                  old_values=old_values, new_values=issue.to_dict())
        db.session.commit()
        
        flash(f'{issue.jira_key} 이슈가 수정되었습니다.', 'success')
        return redirect(url_for('jira.list_issues'))
    
    return render_template('jira/detail.html', form=form, issue=issue, mode='edit')


@jira_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('jira_delete')
def delete(id):
    """이슈 삭제"""
    issue = JiraIssue.query.get_or_404(id)
    old_values = issue.to_dict()
    
    log_audit('DELETE', 'jira_issues', issue.id, old_values=old_values)
    db.session.delete(issue)
    db.session.commit()
    
    flash(f'{issue.jira_key} 이슈가 삭제되었습니다.', 'warning')
    return redirect(url_for('jira.list_issues'))


@jira_bp.route('/paste', methods=['GET', 'POST'])
@login_required
@permission_required('jira_create')
def paste():
    """텍스트 붙여넣기로 이슈 일괄 등록"""
    form = JiraPasteForm()
    result = None
    
    if form.validate_on_submit():
        result = parse_jira_text(form.paste_data.data)
    
    return render_template('jira/paste.html', form=form, result=result)


@jira_bp.route('/paste/save', methods=['POST'])
@login_required
@permission_required('jira_create')
def paste_save():
    """파싱 결과 DB 저장"""
    data = request.get_json()
    
    if not data or 'rows' not in data:
        return jsonify({'success': False, 'message': '데이터가 없습니다.'}), 400
    
    success_count = 0
    fail_count = 0
    errors = []
    
    for idx, row in enumerate(data['rows']):
        try:
            # 중복 체크
            jira_key = row.get('jira_key', '')
            if jira_key:
                existing = JiraIssue.query.filter_by(jira_key=jira_key).first()
                if existing:
                    errors.append({'line': idx + 1, 'message': f'JIRA Key {jira_key} 중복'})
                    fail_count += 1
                    continue
            
            # 담당자 매칭
            assignee_id = None
            assignee_name = row.get('assignee')
            if assignee_name:
                person = Personnel.query.filter_by(name=assignee_name).first()
                if person:
                    assignee_id = person.id
            
            issue = JiraIssue(
                jira_key=jira_key or f'TEMP-{idx+1}',
                summary=row.get('summary', ''),
                description=row.get('description'),
                issue_type=row.get('issue_type', 'Task'),
                priority=row.get('priority', 'Medium'),
                status=row.get('status', 'Open'),
                assignee_id=assignee_id,
                reporter=row.get('reporter'),
                created_date=parse_date(row.get('created_date')),
                resolved_date=parse_date(row.get('resolved_date')),
                due_date=parse_date(row.get('due_date')),
                sprint=row.get('sprint'),
                epic=row.get('epic'),
                labels=row.get('labels'),
                registered_by=current_user.id,
            )
            db.session.add(issue)
            db.session.flush()
            
            log_audit('CREATE', 'jira_issues', issue.id, new_values=issue.to_dict())
            success_count += 1
            
        except Exception as e:
            fail_count += 1
            errors.append({'line': idx + 1, 'message': str(e)})
    
    paste_log = PasteHistory(
        user_id=current_user.id,
        paste_type='jira',
        raw_data=json.dumps(data['rows'], ensure_ascii=False)[:5000],
        success_count=success_count,
        fail_count=fail_count,
        error_details=errors if errors else None,
    )
    db.session.add(paste_log)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'성공: {success_count}건, 실패: {fail_count}건',
        'success_count': success_count,
        'fail_count': fail_count,
        'errors': errors,
    })
