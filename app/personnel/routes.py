"""인원 관리 라우트"""
from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models.personnel import Personnel, Department
from ..utils.decorators import permission_required, role_required
from ..utils.helpers import log_audit, parse_date
from . import personnel_bp
from .forms import PersonnelForm, RetireForm


@personnel_bp.route('/')
@login_required
@role_required('admin', 'manager')
def list_personnel():
    """인원 목록 & 보고용 변동 현황판"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    dept_filter = request.args.get('department', '', type=str)
    status_filter = request.args.get('status', '')
    
    # 1. 인원 기본 조회 쿼리 (재직 중인 유저 위주로 목록에 노출)
    query = Personnel.query
    if search:
        query = query.filter(
            db.or_(
                Personnel.name.contains(search),
                Personnel.employee_id.contains(search),
            )
        )
    if dept_filter:
        query = query.filter(Personnel.department_id == int(dept_filter))
    if status_filter:
        query = query.filter(Personnel.status == status_filter)
    else:
        # 기본 필터링: 재직 및 휴직자 노출 (퇴직자는 하단 리포트에 노출되므로 목록 기본값에선 제외 가능, 혹은 전체 노출)
        pass
        
    pagination = query.order_by(Personnel.status.asc(), Personnel.name.asc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # 2. 이번 달 신규 등록 수 및 퇴사 처리 수 통계 산출 (보고용)
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    
    new_hires_count = Personnel.query.filter(
        Personnel.join_date >= start_of_month,
        Personnel.status == 'active'
    ).count()
    
    retires_count = Personnel.query.filter(
        Personnel.status == 'inactive',
        Personnel.leave_date >= start_of_month
    ).count()
    
    # 3. 최근 퇴사 처리된 인원 명단 (보고용 이력 기록)
    recent_retires = Personnel.query.filter_by(status='inactive')\
        .order_by(Personnel.leave_date.desc())\
        .limit(10).all()
        
    departments = Department.query.filter_by(is_active=True).all()
    
    return render_template('personnel/list.html',
                           personnel=pagination.items,
                           pagination=pagination,
                           departments=departments,
                           search=search,
                           dept_filter=dept_filter,
                           status_filter=status_filter,
                           new_hires_count=new_hires_count,
                           retires_count=retires_count,
                           recent_retires=recent_retires)


@personnel_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('personnel_create')
def create():
    """신규 인원 생성 (5가지 필드만 입력)"""
    form = PersonnelForm()
    
    if form.validate_on_submit():
        # 지역 / 부서 문자열 처리 (없으면 자동 생성)
        dept_name = form.department_name.data.strip()
        dept = Department.query.filter_by(name=dept_name).first()
        if not dept:
            dept = Department(name=dept_name, is_active=True)
            db.session.add(dept)
            db.session.flush()
            
        # 중복 사번(아이디) 체크
        existing = Personnel.query.filter_by(employee_id=form.employee_id.data.strip()).first()
        if existing:
            flash(f"이미 존재하는 사용 아이디({form.employee_id.data})입니다.", 'danger')
            return render_template('personnel/detail.html', form=form, mode='create')
            
        person = Personnel(
            employee_id=form.employee_id.data.strip(),
            name=form.name.data.strip(),
            department_id=dept.id,
            position=form.position.data.strip() if form.position.data else None,
            rank=form.position.data.strip() if form.position.data else None, # 직급도 직위와 같이 매핑
            join_date=form.join_date.data if form.join_date.data else date.today(),
            status='active',
            registered_by=current_user.id,
        )
        db.session.add(person)
        db.session.flush()
        
        log_audit('CREATE', 'personnel', person.id, new_values=person.to_dict())
        db.session.commit()
        
        flash(f'신규 인원 {person.name}님이 정상 등록되었습니다.', 'success')
        return redirect(url_for('personnel.list_personnel'))
        
    return render_template('personnel/detail.html', form=form, mode='create')


@personnel_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('personnel_edit')
def edit(id):
    """인원 수정"""
    person = Personnel.query.get_or_404(id)
    form = PersonnelForm()
    
    if request.method == 'GET':
        form.name.data = person.name
        form.position.data = person.position
        form.join_date.data = person.join_date
        form.employee_id.data = person.employee_id
        form.department_name.data = person.department_name
        
    if form.validate_on_submit():
        old_values = person.to_dict()
        
        # 부서(지역) 처리
        dept_name = form.department_name.data.strip()
        dept = Department.query.filter_by(name=dept_name).first()
        if not dept:
            dept = Department(name=dept_name, is_active=True)
            db.session.add(dept)
            db.session.flush()
            
        # 중복 사번(아이디) 체크 (본인 제외)
        existing = Personnel.query.filter_by(employee_id=form.employee_id.data.strip()).first()
        if existing and existing.id != person.id:
            flash(f"이미 존재하는 사용 아이디({form.employee_id.data})입니다.", 'danger')
            return render_template('personnel/detail.html', form=form, person=person, mode='edit')
            
        person.name = form.name.data.strip()
        person.position = form.position.data.strip() if form.position.data else None
        person.rank = form.position.data.strip() if form.position.data else None
        person.join_date = form.join_date.data if form.join_date.data else date.today()
        person.employee_id = form.employee_id.data.strip()
        person.department_id = dept.id
        
        log_audit('UPDATE', 'personnel', person.id, old_values=old_values, new_values=person.to_dict())
        db.session.commit()
        
        flash(f'{person.name}님의 정보가 수정되었습니다.', 'success')
        return redirect(url_for('personnel.list_personnel'))
        
    return render_template('personnel/detail.html', form=form, person=person, mode='edit')


@personnel_bp.route('/retire', methods=['GET', 'POST'])
@login_required
@permission_required('personnel_edit')
def retire():
    """성함만 입력해서 퇴사 처리"""
    form = RetireForm()
    
    if form.validate_on_submit():
        name = form.name.data.strip()
        leave_date = form.leave_date.data if form.leave_date.data else date.today()
        
        # 재직 중(active)이거나 휴직 중(leave)인 해당 성함의 인원 조회
        active_persons = Personnel.query.filter(
            Personnel.name == name,
            Personnel.status.in_(['active', 'leave'])
        ).all()
        
        if not active_persons:
            flash(f"재직 중인 '{name}' 성함의 인원을 찾을 수 없습니다.", 'warning')
            return render_template('personnel/retire.html', form=form)
            
        # 동명이인이 있는 경우
        if len(active_persons) > 1:
            flash(f"'{name}' 성함의 인원이 여러 명 존재합니다. 동명이인 방지를 위해 목록 뷰에서 특정 사번을 찾아 직접 삭제(수정)해 주세요.", 'danger')
            return render_template('personnel/retire.html', form=form)
            
        # 1명만 존재하는 경우 즉시 퇴사 처리
        person = active_persons[0]
        old_values = person.to_dict()
        
        person.status = 'inactive'
        person.leave_date = leave_date
        
        log_audit('UPDATE', 'personnel', person.id, old_values=old_values, new_values=person.to_dict())
        db.session.commit()
        
        flash(f'{person.name}님이 정상 퇴사(삭제) 처리되었습니다. (퇴사일자: {leave_date})', 'success')
        return redirect(url_for('personnel.list_personnel'))
        
    return render_template('personnel/retire.html', form=form)


@personnel_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('personnel_delete')
def delete(id):
    """목록에서 수동 삭제 처리 (상태를 퇴직 상태로 전환)"""
    person = Personnel.query.get_or_404(id)
    old_values = person.to_dict()
    
    person.status = 'inactive'
    person.leave_date = date.today()
    
    log_audit('DELETE', 'personnel', person.id, old_values=old_values)
    db.session.commit()
    
    flash(f'{person.name}님이 퇴직 처리되었습니다.', 'warning')
    return redirect(url_for('personnel.list_personnel'))
