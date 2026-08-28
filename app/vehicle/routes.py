"""법인차량 운행일지 라우트"""
import csv
import io
from datetime import datetime, date
from urllib.parse import quote
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from flask import render_template, redirect, url_for, flash, request, Response, jsonify, session
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
    is_manager_or_admin = (current_user.is_admin or current_user.is_vehicle_manager or current_user.has_permission('vehicle_manage'))
    if is_manager_or_admin:
        first_vehicle = Vehicle.query.order_by(Vehicle.id.asc()).first()
    else:
        first_vehicle = Vehicle.query.filter_by(is_active=True).order_by(Vehicle.id.asc()).first()

    if first_vehicle:
        return redirect(url_for('vehicle.view_log', vehicle_id=first_vehicle.id))
    flash('등록된 법인차량이 없습니다.', 'warning')
    return redirect(url_for('main.dashboard'))


def sync_vehicle_log_distances(vehicle_id):
    """차량의 모든 운행일지의 주행전/주행후 거리를 시간순(start_time.asc())으로 연쇄 동기화"""
    logs = VehicleLog.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleLog.start_time.asc(), VehicleLog.id.asc()).all()
    if not logs:
        return

    current_odometer = None
    for log in logs:
        if current_odometer is not None:
            log.start_distance = current_odometer
        if log.distance and log.distance > 0:
            log.end_distance = log.start_distance + log.distance
            current_odometer = log.end_distance
        else:
            log.end_distance = log.start_distance
    db.session.commit()


def get_start_dist_ready_map(vehicle_id):
    """
    해당 차량의 로그들을 시간순(start_time.asc())으로 분석하여
    이전 운행자가 주행거리(km)를 마감 기입하였을 때만 다음 운행자의 '주행 전 거리'를 확정(True) 표시하는 맵 생성
    """
    logs = VehicleLog.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleLog.start_time.asc(), VehicleLog.id.asc()).all()
    ready_map = {}
    pending_previous = False

    for log in logs:
        if pending_previous:
            ready_map[log.id] = False
        else:
            ready_map[log.id] = True

        # 이전 운행 건이 아직 마감(주행거리 > 0)되지 않았다면, 이 이후 차례의 주행전 거리는 '대기' 상태로 표시
        if not (log.distance and log.distance > 0):
            pending_previous = True

    return ready_map


def _render_log_page(vehicle_id, form_data=None, edit_form_data=None, edit_log_id=None):
    """차량별 운행일지 조회 및 렌더링 헬퍼 (검증 오류 시 사용자가 기입한 form_data를 보존하여 복원)"""
    _ensure_default_vehicles()
    current_vehicle = Vehicle.query.get_or_404(vehicle_id)

    # 비활성화 차량 접근 제어: 관리자/차량관리자는 비활성화 차량도 조회 가능, 일반 사용자는 활성화 차량만 접근 가능
    is_manager_or_admin = (current_user.is_admin or current_user.is_vehicle_manager or current_user.has_permission('vehicle_manage'))
    if not current_vehicle.is_active and not is_manager_or_admin:
        flash(f"차량 '{current_vehicle.name}'은(는) 현재 비활성화(운행 중단) 상태이므로 일반 사용자는 접근할 수 없습니다.", 'warning')
        first_active = Vehicle.query.filter_by(is_active=True).order_by(Vehicle.id.asc()).first()
        if first_active:
            return redirect(url_for('vehicle.view_log', vehicle_id=first_active.id))
        return redirect(url_for('main.dashboard'))

    if is_manager_or_admin:
        all_vehicles = Vehicle.query.order_by(Vehicle.id.asc()).all()
    else:
        all_vehicles = Vehicle.query.filter_by(is_active=True).order_by(Vehicle.id.asc()).all()

    # 차량의 주행전/후 거리 동기화 및 이전 운행 마감 대기 맵 생성
    sync_vehicle_log_distances(vehicle_id)
    ready_map = get_start_dist_ready_map(vehicle_id)

    page = request.args.get('page', 1, type=int)

    # 운행 목록은 시작시간 순으로 정렬
    pagination = VehicleLog.query.filter_by(vehicle_id=vehicle_id)\
        .order_by(VehicleLog.start_time.desc())\
        .paginate(page=page, per_page=20, error_out=False)

    logs = pagination.items

    # 전체 누적 주행거리 계산 (해당 차량 전체 합산)
    all_logs_for_total = VehicleLog.query.filter_by(vehicle_id=vehicle_id).all()
    total_distance = sum((l.distance or 0.0) for l in all_logs_for_total)

    # 마지막 마감된 주행후 거리를 가져와서 다음 등록 시 주행전거리 기본값으로 세팅
    last_completed = VehicleLog.query.filter_by(vehicle_id=vehicle_id).filter(VehicleLog.distance > 0).order_by(VehicleLog.start_time.desc(), VehicleLog.id.desc()).first()
    if last_completed:
        default_start_distance = last_completed.end_distance
    else:
        first_log = VehicleLog.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleLog.start_time.asc(), VehicleLog.id.asc()).first()
        default_start_distance = first_log.start_distance if first_log else 0.0

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    return render_template('vehicle/log.html',
                           current_vehicle=current_vehicle,
                           all_vehicles=all_vehicles,
                           logs=logs,
                           pagination=pagination,
                           default_start_distance=default_start_distance,
                           total_distance=total_distance,
                           now_str=now_str,
                           ready_map=ready_map,
                           form_data=form_data,
                           edit_form_data=edit_form_data,
                           edit_log_id=edit_log_id)


@vehicle_bp.route('/<int:vehicle_id>')
@login_required
def view_log(vehicle_id):
    """차량별 운행일지 조회 뷰 (20개 단위 페이징 처리 및 엑셀 스타일 디자인)"""
    form_data = session.pop('add_log_form_data', None)
    edit_form_data = session.pop('edit_log_form_data', None)
    edit_log_id = session.pop('edit_log_id', None)
    return _render_log_page(vehicle_id, form_data=form_data, edit_form_data=edit_form_data, edit_log_id=edit_log_id)


@vehicle_bp.route('/<int:vehicle_id>/log/add', methods=['POST'])
@login_required
def add_log(vehicle_id):
    """운행일지 항목 신규 등록 (동일 차량 내 시간 중복 방증 및 시간 선후관계 검증 포함)"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    if not vehicle.is_active:
        session['add_log_form_data'] = request.form.to_dict()
        flash('⚠️ 해당 차량은 현재 비활성화(운행 중단) 상태이므로 신규 운행일지를 등록할 수 없습니다.', 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    start_time = request.form.get('start_time', '').strip().replace('T', ' ')
    end_time = request.form.get('end_time', '').strip().replace('T', ' ')
    department = request.form.get('department', '').strip()
    applicant = request.form.get('applicant', '').strip()
    driver = request.form.get('driver', '').strip()

    if not start_time or not end_time or not applicant:
        session['add_log_form_data'] = request.form.to_dict()
        flash('시작시간, 종료시간 및 신청자 성명은 필수 입력값입니다.', 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    # 요청사항 1: 시작시간보다 종료시간이 빠를 수 없도록 검증
    if end_time <= start_time:
        session['add_log_form_data'] = request.form.to_dict()
        flash('⚠️ 입력 오류: 종료시간은 시작시간보다 이전이거나 같을 수 없습니다.', 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    # 요청사항 2: 현재 날짜보다 이전 날짜를 선택했을 경우 경고 및 차단
    now_date_str = date.today().strftime('%Y-%m-%d')
    if start_time[:10] < now_date_str:
        session['add_log_form_data'] = request.form.to_dict()
        flash(f"⚠️ 입력 오류: 현재 날짜({now_date_str})보다 이전 날짜로는 운행일지를 새로 등록할 수 없습니다. (선택한 날짜: {start_time[:10]})", 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    # 요청사항 2 & 3: 동일 차량 내 시간 중복 검증 (타 차량과는 중복 가능, 동일 차량 중복 시 경고 및 예약자 노출)
    overlap_log = check_time_overlap(vehicle_id, start_time, end_time)
    if overlap_log:
        session['add_log_form_data'] = request.form.to_dict()
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
        end_dist_input = request.form.get('end_distance', '').strip()
        dist_input = request.form.get('distance', '').strip()

        if end_dist_input != '':
            end_distance = float(end_dist_input)
            distance = max(end_distance - start_distance, 0.0)
        elif dist_input != '':
            distance = float(dist_input)
            end_distance = start_distance + distance
        else:
            distance = 0.0
            end_distance = start_distance
    except ValueError:
        start_distance = 0.0
        distance = 0.0
        end_distance = 0.0

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
    sync_vehicle_log_distances(vehicle_id)

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

    new_start_time = request.form.get('start_time', '').strip().replace('T', ' ') or log_item.start_time
    new_end_time = request.form.get('end_time', '').strip().replace('T', ' ') or log_item.end_time

    # 수정 시 시간 검증 및 중복 검증
    if new_end_time <= new_start_time:
        session['edit_log_form_data'] = request.form.to_dict()
        session['edit_log_id'] = log_id
        flash('⚠️ 입력 오류: 종료시간은 시작시간보다 이전이거나 같을 수 없습니다.', 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    now_date_str = date.today().strftime('%Y-%m-%d')
    if new_start_time[:10] < now_date_str:
        session['edit_log_form_data'] = request.form.to_dict()
        session['edit_log_id'] = log_id
        flash(f"⚠️ 입력 오류: 현재 날짜({now_date_str})보다 이전 날짜로는 수정할 수 없습니다. (선택날짜: {new_start_time[:10]})", 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    overlap_log = check_time_overlap(vehicle_id, new_start_time, new_end_time, exclude_log_id=log_id)
    if overlap_log:
        reserved_name = overlap_log.applicant or overlap_log.driver or '사용자미상'
        dept_str = f" ({overlap_log.department})" if overlap_log.department else ""
        flash(
            f"🚨 수정 불가 (시간 중복): [{vehicle.name}] 차량은 이미 [{reserved_name}{dept_str}] 님이 "
            f"'{overlap_log.start_time} ~ {overlap_log.end_time}' 시간대에 예약/운행 중입니다.",
            'danger'
        )
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    log_item.start_time = new_start_time
    log_item.end_time = new_end_time

    if 'applicant' in request.form and request.form.get('applicant', '').strip():
        log_item.applicant = request.form.get('applicant', '').strip()

    if 'driver' in request.form:
        log_item.driver = request.form.get('driver', '').strip()

    if 'purpose' in request.form:
        log_item.purpose = request.form.get('purpose', '').strip()

    if 'notes' in request.form:
        log_item.notes = request.form.get('notes', '').strip()

    dist_val = request.form.get('distance', '').strip()
    end_dist_val = request.form.get('end_distance', '').strip()

    if end_dist_val != '':
        try:
            new_end_dist = float(end_dist_val)
            log_item.end_distance = new_end_dist
            log_item.distance = max(new_end_dist - log_item.start_distance, 0.0)
        except ValueError:
            pass
    elif dist_val != '':
        try:
            new_distance = float(dist_val)
            log_item.distance = new_distance
            log_item.end_distance = log_item.start_distance + new_distance
        except ValueError:
            pass

    db.session.commit()
    sync_vehicle_log_distances(vehicle_id)

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
    sync_vehicle_log_distances(vehicle_id)

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


@vehicle_bp.route('/<int:vehicle_id>/toggle-active', methods=['POST'])
@login_required
@permission_required('vehicle_manage')
def toggle_vehicle_active(vehicle_id):
    """차량관리자/관리자 전용: 차량 비활성화 (운행 중단 & 일반 사용자 숨김) 또는 다시 활성화"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    if vehicle.is_active:
        active_count = Vehicle.query.filter_by(is_active=True).count()
        if active_count <= 1:
            flash('최소 1개 이상의 활성 차량 탭이 유지되어야 하므로 비활성화할 수 없습니다.', 'warning')
            return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    vehicle.is_active = not vehicle.is_active
    db.session.commit()

    status_str = "다시 활성화되었습니다. (모든 일반 사용자에게 노출됨)" if vehicle.is_active else "비활성화되었습니다. (운행 중단 & 일반 사용자 숨김, 관리자만 조회 및 엑셀 출력 가능)"
    log_audit('UPDATE', 'vehicles', vehicle_id, new_values={'is_active': vehicle.is_active, 'name': vehicle.name})

    flash(f"차량 '{vehicle.name}'이(가) {status_str}", 'info' if vehicle.is_active else 'warning')
    return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))


@vehicle_bp.route('/<int:vehicle_id>/delete-vehicle', methods=['POST'])
@login_required
@permission_required('vehicle_manage')
def delete_vehicle(vehicle_id):
    """차량관리자/관리자 전용: 등록된 차량(탭) 및 관련 운행일지 데이터 영구 완전 삭제"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    if vehicle.is_active:
        active_count = Vehicle.query.filter_by(is_active=True).count()
        if active_count <= 1:
            flash('최소 1개 이상의 활성 차량 탭이 유지되어야 하므로 삭제할 수 없습니다.', 'warning')
            return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    v_name = vehicle.name
    v_plate = vehicle.plate_number

    # 차량 및 연관된 운행일지 기록 삭제
    VehicleLog.query.filter_by(vehicle_id=vehicle_id).delete()
    db.session.delete(vehicle)
    db.session.commit()

    log_audit('DELETE', 'vehicles', vehicle_id, old_values={'name': v_name, 'plate_number': v_plate})

    flash(f"차량 '{v_name}'({v_plate}) 및 관련 운행일지 전체가 완전히 영구 삭제되었습니다.", 'danger')

    is_manager_or_admin = (current_user.is_admin or current_user.is_vehicle_manager or current_user.has_permission('vehicle_manage'))
    if is_manager_or_admin:
        next_vehicle = Vehicle.query.order_by(Vehicle.id.asc()).first()
    else:
        next_vehicle = Vehicle.query.filter_by(is_active=True).order_by(Vehicle.id.asc()).first()

    if next_vehicle:
        return redirect(url_for('vehicle.view_log', vehicle_id=next_vehicle.id))
    return redirect(url_for('main.dashboard'))


@vehicle_bp.route('/export-excel', methods=['GET', 'POST'])
@vehicle_bp.route('/<int:vehicle_id>/export-excel', methods=['GET', 'POST'])
@login_required
def export_excel(vehicle_id=None):
    """권한 있는 사용자: 차량별 전용 시트 탭(스타리아, 카니발, 니로, 9669)이 포함된 깔끔한 엑셀(.xlsx) 보고서 생성"""
    raw_vids = request.args.getlist('vehicle_ids') or request.form.getlist('vehicle_ids')
    vehicle_ids = []
    for vid in raw_vids:
        try:
            vehicle_ids.append(int(vid))
        except ValueError:
            pass

    is_manager_or_admin = (current_user.is_admin or current_user.is_vehicle_manager or current_user.has_permission('vehicle_manage'))

    if vehicle_ids:
        if is_manager_or_admin:
            vehicles = Vehicle.query.filter(Vehicle.id.in_(vehicle_ids)).order_by(Vehicle.id.asc()).all()
        else:
            vehicles = Vehicle.query.filter(Vehicle.id.in_(vehicle_ids), Vehicle.is_active == True).order_by(Vehicle.id.asc()).all()
    elif vehicle_id:
        v = Vehicle.query.get(vehicle_id)
        vehicles = [v] if v else []
    else:
        if is_manager_or_admin:
            vehicles = Vehicle.query.order_by(Vehicle.id.asc()).all()
        else:
            vehicles = Vehicle.query.filter_by(is_active=True).order_by(Vehicle.id.asc()).all()

    if not vehicles:
        flash('출력할 차량을 최소 1개 이상 선택해주세요.', 'warning')
        return redirect(url_for('main.dashboard'))

    start_date = request.args.get('start_date', '').strip() or request.form.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip() or request.form.get('end_date', '').strip()

    wb = openpyxl.Workbook()
    default_sheet = wb.active

    # 엑셀 고급 스타일 설정
    header_font = Font(name='맑은 고딕', size=10, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1E293B', end_color='1E293B', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

    summary_font = Font(name='맑은 고딕', size=11, bold=True, color='0F172A')
    summary_fill = PatternFill(start_color='E2E8F0', end_color='E2E8F0', fill_type='solid')

    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    for vehicle in vehicles:
        # 차량 명칭으로 엑셀 시트 탭 생성 (예: 스타리아, 카니발, 니로, 9669)
        ws_title = vehicle.name.replace('/', '_')[:30]
        ws = wb.create_sheet(title=ws_title)

        # 1. 상단 엑셀 타이틀 헤더 블록 (Row 1)
        ws.merge_cells('A1:J1')
        title_cell = ws.cell(row=1, column=1, value=f"법인차량 운행일지 보고서 - {vehicle.name} ({vehicle.plate_number})")
        title_cell.font = Font(name='맑은 고딕', size=14, bold=True, color='FFFFFF')
        title_cell.fill = PatternFill(start_color='1E293B', end_color='1E293B', fill_type='solid')
        title_cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 32

        # 2. 차량 기본 정보 헤더 블록 (Row 2: 차종, 차량번호, 유종, 주의사항)
        ws.merge_cells('A2:J2')
        meta_str = f"① 차종: {vehicle.name}   |   ② 차량번호: {vehicle.plate_number}   |   ③ 유종: {vehicle.fuel_type or '경유'}   |   ④ 주의사항: {vehicle.notice or '안전 운행'}"
        meta_cell = ws.cell(row=2, column=1, value=meta_str)
        meta_cell.font = Font(name='맑은 고딕', size=10, bold=True, color='0369A1')
        meta_cell.fill = PatternFill(start_color='E0F2FE', end_color='E0F2FE', fill_type='solid')
        meta_cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[2].height = 24

        # 3. 공백 구분 행 (Row 3)
        ws.row_dimensions[3].height = 8

        # 4. 운행일지 표 테이블 헤더 (Row 4)
        headers = [
            '시작시간',
            '종료시간',
            '부서',
            '신청자',
            '운전자',
            '주행 전 거리(km)',
            '주행거리(km)',
            '주행 후 거리(km)',
            '용도(구체적 사유)',
            '비고'
        ]

        for col_idx, h_text in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=h_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

        ws.row_dimensions[4].height = 26

        sync_vehicle_log_distances(vehicle.id)
        ready_map = get_start_dist_ready_map(vehicle.id)

        query = VehicleLog.query.filter_by(vehicle_id=vehicle.id)
        if start_date:
            query = query.filter(VehicleLog.start_time >= start_date)
        if end_date:
            query = query.filter(VehicleLog.start_time <= end_date + ' 23:59:59')

        logs = query.order_by(VehicleLog.start_time.asc()).all()

        v_total_dist = 0.0
        current_row = 5

        for log in logs:
            start_dist_val = log.start_distance if ready_map.get(log.id) else "-[이전 운행 마감 대기]-"

            if log.distance and log.distance > 0:
                end_dist_val = log.end_distance
                dist_val = log.distance
                v_total_dist += log.distance
            else:
                if log.start_time and now_str < log.start_time:
                    dist_val = "-[사용 전]-"
                elif log.end_time and now_str > log.end_time:
                    dist_val = "-[거리 미입력]-"
                else:
                    dist_val = "-[운행 중]-"
                end_dist_val = "-"

            row_data = [
                log.start_time or '',
                log.end_time or '',
                log.department or '',
                log.applicant or '',
                log.driver or '',
                start_dist_val,
                dist_val,
                end_dist_val,
                log.purpose or '',
                log.notes or ''
            ]

            ws.append(row_data)

            # 데이터 셀 스타일 및 서식 적용
            for col_idx in range(1, 11):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.font = Font(name='맑은 고딕', size=10)
                cell.border = thin_border

                if col_idx in [1, 2, 3, 4, 5]:
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                elif col_idx in [6, 7, 8]:
                    cell.alignment = Alignment(horizontal='right', vertical='center')
                    if isinstance(cell.value, (int, float)):
                        cell.number_format = '#,##0'
                else:
                    cell.alignment = Alignment(horizontal='left', vertical='center')

            ws.row_dimensions[current_row].height = 20
            current_row += 1

        # 하단 합계 행 추가 (주행거리 컬럼인 7열에 수치 배치)
        period_str = f"{start_date} ~ {end_date}" if (start_date or end_date) else "전체 기간"
        sum_row = [f"[{vehicle.name}] 선택기간 누적 주행거리 합계", '', '', '', '', '', v_total_dist, '', '', '']
        ws.append(sum_row)

        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=6)

        for col_idx in range(1, 11):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.font = summary_font
            cell.fill = summary_fill
            cell.border = thin_border

        sum_label_cell = ws.cell(row=current_row, column=1)
        sum_label_cell.alignment = Alignment(horizontal='center', vertical='center')

        sum_val_cell = ws.cell(row=current_row, column=7)
        sum_val_cell.number_format = '#,##0" km"'
        sum_val_cell.alignment = Alignment(horizontal='right', vertical='center')
        ws.row_dimensions[current_row].height = 24

        # 열 너비 보정: 시작시간과 종료시간 동일폭(18) 맞춤, 용도 및 비고 열 넓직하게 확장
        for col in ws.columns:
            col_idx = col[0].column
            col_letter = get_column_letter(col_idx)

            if col_idx in (1, 2):
                # ① 시작시간, ② 종료시간: 18로 100% 동일하게 균등 배치
                ws.column_dimensions[col_letter].width = 18.5
            elif col_idx in (9, 10):
                # ⑨ 용도(사유), ⑩ 비고: 텍스트 길이에 맞춰 최소 30/25 이상으로 넉넉하게 확장
                max_len = 0
                for cell in col:
                    if cell.row in (1, 2, current_row):  # 타이틀/정보/합계 병합행 제외
                        continue
                    val_str = str(cell.value or '')
                    char_len = 0
                    for char in val_str:
                        if ord(char) > 127:
                            char_len += 2.2
                        else:
                            char_len += 1.0
                    if char_len > max_len:
                        max_len = char_len
                min_w = 32 if col_idx == 9 else 25
                ws.column_dimensions[col_letter].width = max(max_len + 4, min_w)
            elif col_idx in (6, 7, 8):
                ws.column_dimensions[col_letter].width = 16
            elif col_idx in (3, 4, 5):
                ws.column_dimensions[col_letter].width = 13
            else:
                ws.column_dimensions[col_letter].width = 15

    # 기본 생성된 빈 시트 제거
    if default_sheet in wb.worksheets and len(wb.worksheets) > 1:
        wb.remove(default_sheet)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    if len(vehicles) == 1:
        raw_filename = f"Vehicle_Log_{vehicles[0].name}_{start_date or 'ALL'}_to_{end_date or 'ALL'}.xlsx"
    else:
        raw_filename = f"Vehicle_Log_전체차량({len(vehicles)}대)_{start_date or 'ALL'}_to_{end_date or 'ALL'}.xlsx"

    encoded_filename = quote(raw_filename)

    response = Response(output.getvalue(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
    return response
