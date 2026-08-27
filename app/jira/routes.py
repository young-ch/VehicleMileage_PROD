"""JIRA 이슈 관리 라우트"""
import json
from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models.jira import JiraIssue, IssueComment
from ..models.personnel import Personnel
from ..models.user import User
from ..models.audit import PasteHistory
from ..utils.decorators import permission_required
from ..utils.helpers import log_audit, parse_date
from . import jira_bp
from .forms import JiraIssueForm, JiraPasteForm
from .parser import parse_jira_text


def generate_jira_key():
    """JIRA Key 자동 생성 함수 (SMU-X)"""
    # 현재 등록된 가장 높은 ID를 가져옴
    max_id = db.session.query(db.func.max(JiraIssue.id)).scalar() or 0
    next_num = max_id + 1
    new_key = f"SMU-{next_num}"
    # 유니크 충돌 대비 루프 체크
    while JiraIssue.query.filter_by(jira_key=new_key).first() is not None:
        next_num += 1
        new_key = f"SMU-{next_num}"
    return new_key


@jira_bp.route('/')
@login_required
def kanban_board():
    """JIRA 칸반보드 뷰 (관리자는 전체, 일반 사용자는 본인 이슈만)"""
    query = JiraIssue.query
    if not current_user.is_admin:
        query = query.filter(
            db.or_(
                JiraIssue.assignee_id == current_user.id,
                db.and_(
                    JiraIssue.assignee_id.is_(None),
                    JiraIssue.registered_by == current_user.id
                )
            )
        )
        
    all_issues = query.order_by(JiraIssue.updated_at.desc()).all()
    
    # 상태별 그룹화 (기존 영문 데이터 호환 매핑 포함)
    todo = []
    inprogress = []
    hold = []
    done = []
    
    for issue in all_issues:
        status = (issue.status or '').strip().lower()
        # '종료' 또는 'closed' 상태인 이슈는 칸반보드에서 숨김 (목록 뷰에는 유지)
        if status in ('종료', 'closed'):
            continue
        elif status in ('진행', 'in progress', 'inprogress'):
            inprogress.append(issue)
        elif status in ('완료', 'done', 'resolved'):
            done.append(issue)
        elif status in ('보류', 'hold', 'on hold'):
            hold.append(issue)
        else:
            todo.append(issue)  # Open, To Do 등은 모두 시작전으로 분류
            
    return render_template('jira/kanban.html',
                           todo=todo,
                           inprogress=inprogress,
                           hold=hold,
                           done=done)


@jira_bp.route('/list')
@login_required
def list_issues():
    """기존 JIRA 목록 뷰"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    type_filter = request.args.get('type', '')
    
    query = JiraIssue.query
    if not current_user.is_admin:
        query = query.filter(
            db.or_(
                JiraIssue.assignee_id == current_user.id,
                db.and_(
                    JiraIssue.assignee_id.is_(None),
                    JiraIssue.registered_by == current_user.id
                )
            )
        )
    
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


@jira_bp.route('/update-status', methods=['POST'])
@login_required
@permission_required('jira_edit')
def update_status():
    """드래그 앤 드롭으로 상태 실시간 업데이트 API"""
    data = request.get_json()
    if not data or 'issue_id' not in data or 'status' not in data:
        return jsonify({'success': False, 'message': '잘못된 매개변수'}), 400
        
    issue = JiraIssue.query.get_or_404(data['issue_id'])
    
    # 보안 검증: 관리자가 아니면서 본인 담당도 아니고, (미배정이면서 본인이 생성한 이슈)도 아닌 경우 차단
    is_authorized = False
    if current_user.is_admin:
        is_authorized = True
    elif issue.assignee_id == current_user.id:
        is_authorized = True
    elif issue.assignee_id is None and issue.registered_by == current_user.id:
        is_authorized = True
        
    if not is_authorized:
        return jsonify({'success': False, 'message': '해당 이슈의 상태를 변경할 권한이 없습니다.'}), 403
        
    old_status = issue.status
    new_status = data['status']
    
    if old_status != new_status:
        issue.status = new_status
        log_audit('UPDATE', 'jira_issues', issue.id,
                  old_values={'status': old_status},
                  new_values={'status': new_status})
        db.session.commit()
        
    return jsonify({'success': True, 'message': f'{issue.jira_key} 상태가 {new_status}(으)로 변경되었습니다.'})


@jira_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('jira_create')
def create():
    """이슈 개별 등록"""
    form = JiraIssueForm()
    form.assignee_id.choices = [(0, '선택하세요')] + [
        (u.id, u.username) 
        for u in User.query.filter_by(is_active=True).all()
    ]
    
    if form.validate_on_submit():
        # JIRA Key 자동 생성
        j_key = generate_jira_key()
            
        # 생성일이 비어있으면 오늘 날짜 기본 입력
        c_date = form.created_date.data if form.created_date.data else date.today()

        issue = JiraIssue(
            jira_key=j_key,
            summary=form.summary.data,
            description=form.description.data,
            issue_type=form.issue_type.data,
            priority=form.priority.data,
            status=form.status.data,
            assignee_id=form.assignee_id.data if form.assignee_id.data != 0 else None,
            reporter=form.reporter.data,
            created_date=c_date,
            resolved_date=form.resolved_date.data,
            due_date=form.due_date.data,
            sprint=None,
            epic=None,
            labels=form.labels.data,
            registered_by=current_user.id,
        )
        db.session.add(issue)
        db.session.flush()
        
        log_audit('CREATE', 'jira_issues', issue.id, new_values=issue.to_dict())
        db.session.commit()
        
        flash(f'{issue.jira_key} 이슈가 등록되었습니다.', 'success')
        return redirect(url_for('jira.kanban_board'))
    
    # 폼 생성 시 생성일(created_date)의 기본값으로 오늘 날짜 설정 및 담당자 기본값 설정
    if request.method == 'GET':
        form.created_date.data = date.today()
        form.assignee_id.data = 0
        
    return render_template('jira/detail.html', form=form, mode='create')


@jira_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('jira_edit')
def edit(id):
    """이슈 수정"""
    issue = JiraIssue.query.get_or_404(id)
    
    # 보안 검증: 관리자가 아니면서 본인 담당도 아니고, (미배정이면서 본인이 생성한 이슈)도 아닌 경우 차단
    is_authorized = False
    if current_user.is_admin:
        is_authorized = True
    elif issue.assignee_id == current_user.id:
        is_authorized = True
    elif issue.assignee_id is None and issue.registered_by == current_user.id:
        is_authorized = True
        
    if not is_authorized:
        flash('해당 이슈를 수정할 권한이 없습니다.', 'danger')
        return redirect(url_for('jira.kanban_board'))
        
    # 유효한 유저 ID 목록 취득 및 셀렉트 박스 초이스 제공
    active_users = User.query.filter_by(is_active=True).all()
    valid_user_ids = [u.id for u in active_users]
    
    form = JiraIssueForm(obj=issue)
    form.assignee_id.choices = [(0, '선택하세요')] + [
        (u.id, u.username)
        for u in active_users
    ]
    
    # DB의 assignee_id가 None이거나 현재 가입된 회원 ID가 아니면 0(선택 안함)으로 강제 보정
    if request.method == 'GET':
        if issue.assignee_id is None or issue.assignee_id not in valid_user_ids:
            form.assignee_id.data = 0
        
    if form.validate_on_submit():
        old_values = issue.to_dict()
        
        # 임시 변수에 폼 데이터 백업 후 수동 저장
        assignee_val = form.assignee_id.data
        form.populate_obj(issue)
        
        # 0(선택안함)이면 DB에는 None으로 기록
        if assignee_val == 0 or assignee_val is None:
            issue.assignee_id = None
        else:
            issue.assignee_id = assignee_val
        
        # 수정 시에도 에픽/스프린트는 null 유지
        issue.sprint = None
        issue.epic = None
        
        # '종료' 상태로 변경되었는데 해결일이 없는 경우 오늘 날짜로 자동 기록
        if (issue.status or '').strip().lower() in ('종료', 'closed') and not issue.resolved_date:
            issue.resolved_date = date.today()
        
        log_audit('UPDATE', 'jira_issues', issue.id,
                  old_values=old_values, new_values=issue.to_dict())
        db.session.commit()
        
        flash(f'{issue.jira_key} 이슈가 수정되었습니다.', 'success')
        return redirect(url_for('jira.kanban_board'))
    
    return render_template('jira/detail.html', form=form, issue=issue, mode='edit')


@jira_bp.route('/<int:id>/close', methods=['POST'])
@login_required
@permission_required('jira_edit')
def close_issue(id):
    """이슈종료 버튼 클릭 시 빠른 종료 처리 (칸반보드에서는 숨겨지고 목록 뷰에는 유지)"""
    issue = JiraIssue.query.get_or_404(id)
    
    # 보안 검증: 관리자, 담당자, 또는 (미배정 & 생성자)만 허용
    is_authorized = False
    if current_user.is_admin:
        is_authorized = True
    elif issue.assignee_id == current_user.id:
        is_authorized = True
    elif issue.assignee_id is None and issue.registered_by == current_user.id:
        is_authorized = True
        
    if not is_authorized:
        flash('해당 이슈를 종료할 권한이 없습니다.', 'danger')
        return redirect(url_for('jira.kanban_board'))
        
    old_values = issue.to_dict()
    issue.status = '종료'
    if not issue.resolved_date:
        issue.resolved_date = date.today()
        
    log_audit('UPDATE', 'jira_issues', issue.id,
              old_values=old_values, new_values=issue.to_dict())
    db.session.commit()
    
    flash(f'{issue.jira_key} 이슈가 종료되었습니다. (칸반보드에서 제외되고 목록 뷰에 저장됩니다)', 'info')
    return redirect(url_for('jira.kanban_board'))


@jira_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('jira_delete')
def delete(id):
    """이슈 삭제"""
    issue = JiraIssue.query.get_or_404(id)
    
    # 보안 검증: 관리자가 아니면서 본인 담당도 아니고, (미배정이면서 본인이 생성한 이슈)도 아닌 경우 차단
    is_authorized = False
    if current_user.is_admin:
        is_authorized = True
    elif issue.assignee_id == current_user.id:
        is_authorized = True
    elif issue.assignee_id is None and issue.registered_by == current_user.id:
        is_authorized = True
        
    if not is_authorized:
        flash('해당 이슈를 삭제할 권한이 없습니다.', 'danger')
        return redirect(url_for('jira.kanban_board'))
        
    old_values = issue.to_dict()
    
    log_audit('DELETE', 'jira_issues', issue.id, old_values=old_values)
    db.session.delete(issue)
    db.session.commit()
    
    flash(f'{issue.jira_key} 이슈가 삭제되었습니다.', 'warning')
    return redirect(url_for('jira.kanban_board'))


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
            jira_key = jira_key.strip() if jira_key else ""
            
            # JIRA Key가 없으면 파싱 저장할 때도 자동 생성
            if not jira_key:
                jira_key = generate_jira_key()
            else:
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
            
            # 생성일 설정 (없으면 오늘 날짜)
            created_val = parse_date(row.get('created_date'))
            if not created_val:
                created_val = date.today()
            
            issue = JiraIssue(
                jira_key=jira_key,
                summary=row.get('summary', ''),
                description=row.get('description'),
                issue_type=row.get('issue_type', 'Task'),
                priority=row.get('priority', 'Medium'),
                status=row.get('status', 'Open'),
                assignee_id=assignee_id,
                reporter=row.get('reporter'),
                created_date=created_val,
                resolved_date=parse_date(row.get('resolved_date')),
                due_date=parse_date(row.get('due_date')),
                sprint=None,
                epic=None,
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
