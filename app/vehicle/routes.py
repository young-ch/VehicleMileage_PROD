"""법인차량 운행일지 라우트"""
import csv
import io
from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, Response, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models.vehicle import Vehicle, VehicleLog
from ..models.user import User
from ..utils.decorators import role_required, permission_required
from ..utils.helpers import log_audit
from . import vehicle_bp


def _ensure_default_vehicles():
    """기본 법인차량 목록이 없으면 생성 (스타리아, 카니발, 니로, 9669)"""
    if Vehicle.query.count() == 0:
        defaults = [
            {'name': '스타리아', 'plate_number': '160하8962', 'fuel_type': '경유', 'notice': '사용후 반드시 본관앞 주차!! 연료 50% 이하시 주유!!'},
            {'name': '카니발', 'plate_number': '123가4567', 'fuel_type': '경유', 'notice': '사용후 반드시 지정 주차구역 주차!'},
            {'name': '니로', 'plate_number': '987나6543', 'fuel_type': '휘발유', 'notice': '연료 충전 및 청결 유지 필수!'},
            {'name': '9669', 'plate_number': '9669', 'fuel_type': '경유', 'notice': '장거리 운행 전 타이어 공기압 점검!'}
        ]
        for v in defaults:
            vehicle = Vehicle(**v)
            db.session.add(vehicle)
        db.session.commit()


def check_time_overlap(vehicle_id, start_time, end_time, exclude_log_id=None):
    """동일 차량 내 운행 시간 중복 검증 함수"""
    if not start_time or not end_time:
        return None

    query = VehicleLog.query.filter_by(vehicle_id=vehicle_id)
    if exclude_log_id:
        query = query.filter(VehicleLog.id != exclude_log_id)

    existing_logs = query.all()
    for ex in existing_logs:
        if ex.start_time and ex.end_time:
            # 시간대 중복 조건: new_start < ex_end and new_end > ex_start
            if start_time < ex.end_time and end_time > ex.start_time:
                return ex
    return None


@vehicle_bp.route('/')
@login_required
def index():
    """기본 법인차량 운행일지 페이지 (첫 번째 차량으로 리다이렉트)"""
    _ensure_default_vehicles()
    first_vehicle = Vehicle.query.filter_by(is_active=True).first()
    if first_vehicle:
        return redirect(url_for('vehicle.view_log', vehicle_id=first_vehicle.id))
    flash('등록된 법인차량이 없습니다.', 'warning')
    return redirect(url_for('main.dashboard'))


@vehicle_bp.route('/<int:vehicle_id>')
@login_required
def view_log(vehicle_id):
    """차량별 운행일지 조회 뷰 (20개 단위 페이징 처리 및 엑셀 스타일 디자인)"""
    _ensure_default_vehicles()
    current_vehicle = Vehicle.query.get_or_404(vehicle_id)
    all_vehicles = Vehicle.query.filter_by(is_active=True).order_by(Vehicle.id.asc()).all()

    page = request.args.get('page', 1, type=int)

    # 요청사항 2: 운행 목록은 시작시간 순으로 정렬
    pagination = VehicleLog.query.filter_by(vehicle_id=vehicle_id)\
        .order_by(VehicleLog.start_time.desc())\
        .paginate(page=page, per_page=20, error_out=False)

    logs = pagination.items

    # 전체 누적 주행거리 계산 (해당 차량 전체 합산)
    all_logs_for_total = VehicleLog.query.filter_by(vehicle_id=vehicle_id).all()
    total_distance = sum(l.distance for l in all_logs_for_total)

    # 마지막 등록된 주행후 거리를 가져와서 다음 등록 시 주행전거리 기본값으로 세팅
    last_log = VehicleLog.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleLog.id.desc()).first()
    default_start_distance = last_log.end_distance if last_log else 0.0

    return render_template('vehicle/log.html',
                           current_vehicle=current_vehicle,
                           all_vehicles=all_vehicles,
                           logs=logs,
                           pagination=pagination,
                           default_start_distance=default_start_distance,
                           total_distance=total_distance)


@vehicle_bp.route('/<int:vehicle_id>/log/add', methods=['POST'])
@login_required
def add_log(vehicle_id):
    """운행일지 항목 신규 등록 (동일 차량 내 시간 중복 방증 및 시간 선후관계 검증 포함)"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    start_time = request.form.get('start_time', '').strip().replace('T', ' ')
    end_time = request.form.get('end_time', '').strip().replace('T', ' ')
    department = request.form.get('department', '').strip()
    applicant = request.form.get('applicant', '').strip()
    driver = request.form.get('driver', '').strip()

    if not start_time or not end_time or not applicant:
        flash('시작시간, 종료시간 및 신청자 성명은 필수 입력값입니다.', 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    # 요청사항 1: 시작시간보다 종료시간이 빠를 수 없도록 검증
    if end_time <= start_time:
        flash('⚠️ 입력 오류: 종료시간은 시작시간보다 이전이거나 같을 수 없습니다.', 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    # 요청사항 2: 현재 날짜보다 이전 날짜를 선택했을 경우 경고 및 차단
    now_date_str = date.today().strftime('%Y-%m-%d')
    if start_time[:10] < now_date_str:
        flash(f"⚠️ 입력 오류: 현재 날짜({now_date_str})보다 이전 날짜로는 운행일지를 새로 등록할 수 없습니다. (선택한 날짜: {start_time[:10]})", 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    # 요청사항 2 & 3: 동일 차량 내 시간 중복 검증 (타 차량과는 중복 가능, 동일 차량 중복 시 경고 및 예약자 노출)
    overlap_log = check_time_overlap(vehicle_id, start_time, end_time)
    if overlap_log:
        reserved_name = overlap_log.applicant or overlap_log.driver or '사용자미상'
        dept_str = f" ({overlap_log.department})" if overlap_log.department else ""
        flash(
            f"🚨 예약 불가 (시간 중복): [{vehicle.name}] 차량은 이미 [{reserved_name}{dept_str}] 님이 "
            f"'{overlap_log.start_time} ~ {overlap_log.end_time}' 시간대에 예약/운행 중입니다.",
            'danger'
        )
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    try:
        start_distance = float(request.form.get('start_distance', 0) or 0)
        distance = float(request.form.get('distance', 0) or 0)
    except ValueError:
        start_distance = 0.0
        distance = 0.0

    end_distance = start_distance + distance
    purpose = request.form.get('purpose', '').strip()
    notes = request.form.get('notes', '').strip()

    new_log = VehicleLog(
        vehicle_id=vehicle_id,
        start_time=start_time,
        end_time=end_time,
        department=department,
        applicant=applicant,
        driver=driver,
        start_distance=start_distance,
        end_distance=end_distance,
        distance=distance,
        purpose=purpose,
        notes=notes,
        registered_by=current_user.id
    )

    db.session.add(new_log)
    db.session.commit()

    log_audit('CREATE', 'vehicle_logs', new_log.id, new_values={
        'vehicle': vehicle.name,
        'driver': driver,
        'distance': distance
    })

    flash(f'{vehicle.name} 운행일지가 등록되었습니다. (시간: {start_time} ~ {end_time})', 'success')
    return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))


@vehicle_bp.route('/log/<int:log_id>/edit', methods=['POST'])
@login_required
def edit_log(log_id):
    """운행일지 리스트 항목 수정 (동일 차량 시간 중복 검증 포함)"""
    log_item = VehicleLog.query.get_or_404(log_id)
    vehicle_id = log_item.vehicle_id
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    if not current_user.is_admin and not current_user.is_vehicle_manager and log_item.registered_by != current_user.id:
        flash('본인이 등록한 일지 또는 차량관리자만 수정할 수 있습니다.', 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    new_end_time = request.form.get('end_time', '').strip().replace('T', ' ')
    start_time = log_item.start_time

    # 수정 시 시간 검증 및 중복 검증
    if new_end_time:
        if new_end_time <= start_time:
            flash('⚠️ 입력 오류: 종료시간은 시작시간보다 이전이거나 같을 수 없습니다.', 'danger')
            return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

        now_date_str = date.today().strftime('%Y-%m-%d')
        if new_end_time[:10] < now_date_str:
            flash(f"⚠️ 입력 오류: 현재 날짜({now_date_str})보다 이전 날짜로는 수정할 수 없습니다.", 'danger')
            return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

        overlap_log = check_time_overlap(vehicle_id, start_time, new_end_time, exclude_log_id=log_id)
        if overlap_log:
            reserved_name = overlap_log.applicant or overlap_log.driver or '사용자미상'
            dept_str = f" ({overlap_log.department})" if overlap_log.department else ""
            flash(
                f"🚨 수정 불가 (시간 중복): [{vehicle.name}] 차량은 이미 [{reserved_name}{dept_str}] 님이 "
                f"'{overlap_log.start_time} ~ {overlap_log.end_time}' 시간대에 예약/운행 중입니다.",
                'danger'
            )
            return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))
        log_item.end_time = new_end_time

    if 'driver' in request.form:
        log_item.driver = request.form.get('driver', '').strip()

    if 'purpose' in request.form:
        log_item.purpose = request.form.get('purpose', '').strip()

    if 'notes' in request.form:
        log_item.notes = request.form.get('notes', '').strip()

    dist_val = request.form.get('distance', '').strip()
    if dist_val != '':
        try:
            new_distance = float(dist_val)
            log_item.distance = new_distance
            log_item.end_distance = log_item.start_distance + new_distance
        except ValueError:
            pass

    db.session.commit()

    log_audit('UPDATE', 'vehicle_logs', log_item.id, new_values={
        'end_time': log_item.end_time,
        'driver': log_item.driver,
        'distance': log_item.distance
    })

    flash('운행일지 기록이 성공적으로 수정되었습니다.', 'success')
    return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))


@vehicle_bp.route('/log/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_log(log_id):
    """잘못 입력된 운행일지 리스트 항목 삭제"""
    log_item = VehicleLog.query.get_or_404(log_id)
    vehicle_id = log_item.vehicle_id

    log_audit('DELETE', 'vehicle_logs', log_item.id, old_values={
        'applicant': log_item.applicant,
        'distance': log_item.distance
    })

    db.session.delete(log_item)
    db.session.commit()

    flash('운행일지 기록이 삭제되었습니다.', 'warning')
    return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))


@vehicle_bp.route('/add-vehicle', methods=['POST'])
@login_required
@permission_required('vehicle_manage')
def add_vehicle():
    """요청사항 4: 차량관리자/관리자 전용 차량 신규 추가 (새 탭 자동 생성)"""
    name = request.form.get('name', '').strip()
    plate_number = request.form.get('plate_number', '').strip()
    fuel_type = request.form.get('fuel_type', '경유').strip()
    notice = request.form.get('notice', '사용후 반드시 지정 위치 주차!').strip()

    if not name or not plate_number:
        flash('차종 명칭과 차량번호는 필수 입력항목입니다.', 'danger')
        return redirect(url_for('vehicle.index'))

    new_vehicle = Vehicle(
        name=name,
        plate_number=plate_number,
        fuel_type=fuel_type,
        notice=notice,
        is_active=True
    )
    db.session.add(new_vehicle)
    db.session.commit()

    log_audit('CREATE', 'vehicles', new_vehicle.id, new_values=new_vehicle.to_dict())
    flash(f"신규 차량 '{name}'({plate_number})이 성공적으로 추가되어 전용 탭이 생성되었습니다.", 'success')
    return redirect(url_for('vehicle.view_log', vehicle_id=new_vehicle.id))


@vehicle_bp.route('/<int:vehicle_id>/update-info', methods=['POST'])
@login_required
@permission_required('vehicle_manage')
def update_vehicle_info(vehicle_id):
    """차량관리자/관리자 전용: 차종, 차량번호, 유종, 주의문구 수정"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    vehicle.name = request.form.get('name', vehicle.name).strip()
    vehicle.plate_number = request.form.get('plate_number', vehicle.plate_number).strip()
    vehicle.fuel_type = request.form.get('fuel_type', vehicle.fuel_type).strip()
    vehicle.notice = request.form.get('notice', vehicle.notice).strip()

    db.session.commit()

    log_audit('UPDATE', 'vehicles', vehicle.id, new_values=vehicle.to_dict())
    flash(f'{vehicle.name} 차량 기본 정보가 관리자 권한으로 변경되었습니다.', 'info')
    return redirect(url_for('vehicle.view_log', vehicle_id=vehicle.id))


@vehicle_bp.route('/<int:vehicle_id>/delete-vehicle', methods=['POST'])
@login_required
@permission_required('vehicle_manage')
def delete_vehicle(vehicle_id):
    """차량관리자/관리자 전용: 등록된 차량(탭) 완전 삭제"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    active_count = Vehicle.query.filter_by(is_active=True).count()
    if active_count <= 1:
        flash('최소 1개 이상의 차량 탭이 유지되어야 하므로 삭제할 수 없습니다.', 'warning')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    v_name = vehicle.name
    v_plate = vehicle.plate_number

    # 차량 및 연관된 운행일지 기록 삭제
    VehicleLog.query.filter_by(vehicle_id=vehicle_id).delete()
    db.session.delete(vehicle)
    db.session.commit()

    log_audit('DELETE', 'vehicles', vehicle_id, old_values={'name': v_name, 'plate_number': v_plate})

    flash(f"차량 '{v_name}'({v_plate}) 및 관련 운행일지 전체가 완전히 삭제되었습니다.", 'danger')

    next_vehicle = Vehicle.query.filter_by(is_active=True).first()
    if next_vehicle:
        return redirect(url_for('vehicle.view_log', vehicle_id=next_vehicle.id))
    return redirect(url_for('main.dashboard'))


@vehicle_bp.route('/<int:vehicle_id>/export-excel', methods=['GET', 'POST'])
@login_required
def export_excel(vehicle_id):
    """권한 있는 사용자: 날짜 범위 지정 엑셀(.csv) 출력 양식 생성"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    start_date = request.args.get('start_date', '').strip() or request.form.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip() or request.form.get('end_date', '').strip()

    query = VehicleLog.query.filter_by(vehicle_id=vehicle_id)

    if start_date:
        query = query.filter(VehicleLog.start_time >= start_date)
    if end_date:
        query = query.filter(VehicleLog.start_time <= end_date + ' 23:59:59')

    # 시작시간 순차 정렬로 엑셀 보고서 출력
    logs = query.order_by(VehicleLog.start_time.asc()).all()

    output = io.StringIO()
    output.write('\uFEFF')  # UTF-8 BOM (한글 깨짐 방지)
    writer = csv.writer(output)

    # 엑셀 1행: 차종, 차량번호, 유종, 주의사항 양식
    writer.writerow(['① 차종', vehicle.name, '', '차량번호', vehicle.plate_number, '', '유종', vehicle.fuel_type, '', vehicle.notice])
    writer.writerow([])

    # 엑셀 3행: 표 헤더 항목
    writer.writerow([
        '② 시작시간',
        '③ 종료시간',
        '④ 사용자 - 부서',
        '④ 사용자 - 신청자',
        '④ 사용자 - 운전자',
        '⑤ 주행 전 계기판 거리(km)',
        '⑥ 주행 후 계기판 거리(km)',
        '⑦ 주행거리(km)',
        '⑧ 용도 (구체적 사유)',
        '비고 (충전필요, 사고여부 등)'
    ])

    for log in logs:
        writer.writerow([
            log.start_time or '',
            log.end_time or '',
            log.department or '',
            log.applicant or '',
            log.driver or '',
            f"{log.start_distance:,.0f}" if log.start_distance else "0",
            f"{log.end_distance:,.0f}" if log.end_distance else "0",
            f"{log.distance:,.0f}" if log.distance else "0",
            log.purpose or '',
            log.notes or ''
        ])

    total_dist = sum(l.distance for l in logs)
    writer.writerow([])

    period_str = f"{start_date} ~ {end_date}" if (start_date or end_date) else "전체 기간"
    writer.writerow([f'선택 기간 ({period_str}) 누적 주행거리 합계', '', '', '', '', '', '', f"{total_dist:,.0f} km", '', ''])

    response = Response(output.getvalue(), mimetype='text/csv')
    filename = f"Vehicle_Log_{vehicle.name}_{start_date or 'ALL'}_to_{end_date or 'ALL'}.csv"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response
