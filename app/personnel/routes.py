"""인원 관리 라우트"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models.personnel import Personnel, Department
from ..models.audit import PasteHistory
from ..utils.decorators import permission_required, role_required
from ..utils.helpers import log_audit, parse_date
from . import personnel_bp
from .forms import PersonnelForm, PersonnelPasteForm
from .parser import parse_personnel_text


@personnel_bp.route('/')
@login_required
@role_required('admin', 'manager')
def list_personnel():
    """인원 목록"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    dept_filter = request.args.get('department', '', type=str)
    status_filter = request.args.get('status', '', type=str)
    
    query = Personnel.query
    
    if search:
        query = query.filter(
            db.or_(
                Personnel.name.contains(search),
                Personnel.employee_id.contains(search),
                Personnel.email.contains(search),
            )
        )
    if dept_filter:
        query = query.filter(Personnel.department_id == int(dept_filter))
    if status_filter:
        query = query.filter(Personnel.status == status_filter)
    
    pagination = query.order_by(Personnel.name).paginate(
        page=page, per_page=20, error_out=False
    )
    
    departments = Department.query.filter_by(is_active=True).all()
    
    return render_template('personnel/list.html',
                           personnel=pagination.items,
                           pagination=pagination,
                           departments=departments,
                           search=search,
                           dept_filter=dept_filter,
                           status_filter=status_filter)


@personnel_bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('personnel_create')
def create():
    """인원 개별 등록"""
    form = PersonnelForm()
    form.department_id.choices = [(0, '선택하세요')] + [
        (d.id, d.name) for d in Department.query.filter_by(is_active=True).all()
    ]
    
    if form.validate_on_submit():
        person = Personnel(
            employee_id=form.employee_id.data,
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            department_id=form.department_id.data if form.department_id.data != 0 else None,
            position=form.position.data,
            rank=form.rank.data,
            join_date=form.join_date.data,
            leave_date=form.leave_date.data,
            status=form.status.data,
            registered_by=current_user.id,
        )
        db.session.add(person)
        db.session.flush()
        
        log_audit('CREATE', 'personnel', person.id, new_values=person.to_dict())
        db.session.commit()
        
        flash(f'{person.name}님이 등록되었습니다.', 'success')
        return redirect(url_for('personnel.list_personnel'))
    
    return render_template('personnel/detail.html', form=form, mode='create')


@personnel_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('personnel_edit')
def edit(id):
    """인원 수정"""
    person = Personnel.query.get_or_404(id)
    form = PersonnelForm(obj=person)
    form.department_id.choices = [(0, '선택하세요')] + [
        (d.id, d.name) for d in Department.query.filter_by(is_active=True).all()
    ]
    
    if form.validate_on_submit():
        old_values = person.to_dict()
        
        form.populate_obj(person)
        if form.department_id.data == 0:
            person.department_id = None
        
        log_audit('UPDATE', 'personnel', person.id,
                  old_values=old_values, new_values=person.to_dict())
        db.session.commit()
        
        flash(f'{person.name}님의 정보가 수정되었습니다.', 'success')
        return redirect(url_for('personnel.list_personnel'))
    
    return render_template('personnel/detail.html', form=form, person=person, mode='edit')


@personnel_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('personnel_delete')
def delete(id):
    """인원 삭제 (소프트 삭제 - 상태 변경)"""
    person = Personnel.query.get_or_404(id)
    old_values = person.to_dict()
    
    person.status = 'inactive'
    log_audit('DELETE', 'personnel', person.id, old_values=old_values)
    db.session.commit()
    
    flash(f'{person.name}님이 비활성 처리되었습니다.', 'warning')
    return redirect(url_for('personnel.list_personnel'))


@personnel_bp.route('/paste', methods=['GET', 'POST'])
@login_required
@permission_required('personnel_create')
def paste():
    """텍스트 붙여넣기로 인원 일괄 등록"""
    form = PersonnelPasteForm()
    result = None
    
    if form.validate_on_submit():
        result = parse_personnel_text(form.paste_data.data)
    
    return render_template('personnel/paste.html', form=form, result=result)


@personnel_bp.route('/paste/save', methods=['POST'])
@login_required
@permission_required('personnel_create')
def paste_save():
    """파싱 결과 DB 저장"""
    import json
    data = request.get_json()
    
    if not data or 'rows' not in data:
        return jsonify({'success': False, 'message': '데이터가 없습니다.'}), 400
    
    success_count = 0
    fail_count = 0
    errors = []
    
    for idx, row in enumerate(data['rows']):
        try:
            # 부서 처리 (없으면 생성)
            dept = None
            dept_name = row.get('department')
            if dept_name:
                dept = Department.query.filter_by(name=dept_name).first()
                if not dept:
                    dept = Department(name=dept_name, is_active=True)
                    db.session.add(dept)
                    db.session.flush()
            
            # 중복 체크
            existing = Personnel.query.filter_by(employee_id=row.get('employee_id')).first()
            if existing:
                errors.append({'line': idx + 1, 'message': f"사번 {row.get('employee_id')} 중복"})
                fail_count += 1
                continue
            
            person = Personnel(
                employee_id=row.get('employee_id', ''),
                name=row.get('name', ''),
                email=row.get('email'),
                phone=row.get('phone'),
                department_id=dept.id if dept else None,
                position=row.get('position'),
                rank=row.get('rank'),
                join_date=parse_date(row.get('join_date')),
                status=row.get('status', 'active'),
                registered_by=current_user.id,
            )
            db.session.add(person)
            db.session.flush()
            
            log_audit('CREATE', 'personnel', person.id, new_values=person.to_dict())
            success_count += 1
            
        except Exception as e:
            fail_count += 1
            errors.append({'line': idx + 1, 'message': str(e)})
    
    # 붙여넣기 이력 저장
    paste_log = PasteHistory(
        user_id=current_user.id,
        paste_type='personnel',
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
