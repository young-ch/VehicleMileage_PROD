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
    """차량별 운행일지 조회 뷰 (엑셀 스타일 디자인)"""
    _ensure_default_vehicles()
    current_vehicle = Vehicle.query.get_or_404(vehicle_id)
    all_vehicles = Vehicle.query.filter_by(is_active=True).order_by(Vehicle.id.asc()).all()

    # 해당 차량의 운행일지 리스트 (최근순 또는 생성순)
    logs = VehicleLog.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleLog.created_at.asc()).all()

    # 마지막 등록된 주행후 거리를 가져와서 다음 등록 시 주행전거리 기본값으로 세팅
    last_log = VehicleLog.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleLog.id.desc()).first()
    default_start_distance = last_log.end_distance if last_log else 0.0

    # 총 누적 주행거리 계산
    total_distance = sum(l.distance for l in logs)

    return render_template('vehicle/log.html',
                           current_vehicle=current_vehicle,
                           all_vehicles=all_vehicles,
                           logs=logs,
                           default_start_distance=default_start_distance,
                           total_distance=total_distance)


@vehicle_bp.route('/<int:vehicle_id>/log/add', methods=['POST'])
@login_required
def add_log(vehicle_id):
    """운행일지 항목 신규 등록 (주행후 = 주행전 + 주행거리 자동 계산 적용)"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    start_time = request.form.get('start_time', '').strip()
    end_time = request.form.get('end_time', '').strip()
    department = request.form.get('department', '').strip()
    applicant = request.form.get('applicant', '').strip()
    driver = request.form.get('driver', '').strip()
    
    try:
        start_distance = float(request.form.get('start_distance', 0) or 0)
        distance = float(request.form.get('distance', 0) or 0)
    except ValueError:
        start_distance = 0.0
        distance = 0.0

    # 핵심 로직: 주행후 = 주행전 + 주행거리
    end_distance = start_distance + distance

    purpose = request.form.get('purpose', '').strip()
    notes = request.form.get('notes', '').strip()

    if not start_time or not applicant:
        flash('시작시간 및 신청자 성명은 필수 입력값입니다.', 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

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

    flash(f'{vehicle.name} 운행일지가 등록되었습니다. (주행거리: {distance} km)', 'success')
    return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))


@vehicle_bp.route('/log/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_log(log_id):
    """잘못 입력된 운행일지 리스트 항목 삭제"""
    log_item = VehicleLog.query.get_or_404(log_id)
    vehicle_id = log_item.vehicle_id

    # 작성자 본인 또는 차량관리자/관리자만 삭제 가능
    if not current_user.is_admin and not current_user.is_vehicle_manager and log_item.registered_by != current_user.id:
        flash('본인이 등록한 일지 또는 차량관리자 권한 보유자만 삭제할 수 있습니다.', 'danger')
        return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))

    log_audit('DELETE', 'vehicle_logs', log_item.id, old_values={
        'applicant': log_item.applicant,
        'distance': log_item.distance
    })

    db.session.delete(log_item)
    db.session.commit()

    flash('운행일지 기록이 삭제되었습니다.', 'warning')
    return redirect(url_for('vehicle.view_log', vehicle_id=vehicle_id))


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


@vehicle_bp.route('/<int:vehicle_id>/export-excel')
@login_required
def export_excel(vehicle_id):
    """권한 있는 사용자: 이미지 엑셀 양식과 동일하게 엑셀(CSV) 출력"""
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    logs = VehicleLog.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleLog.created_at.asc()).all()

    output = io.StringIO()
    # UTF-8 BOM 서명으로 엑셀 한글 깨짐 방지
    output.write('\uFEFF')
    writer = csv.writer(output)

    # 1. 엑셀 상단 헤더 정보 (차종, 차량번호, 유종, 주의사항)
    writer.writerow(['① 차종', vehicle.name, '', '차량번호', vehicle.plate_number, '', '유종', vehicle.fuel_type, '', vehicle.notice])
    writer.writerow([])  # 빈 줄

    # 2. 운행일지 세부 컬럼 헤더
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

    # 3. 데이터 행 출력
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

    # 4. 누적합계 출력
    total_dist = sum(l.distance for l in logs)
    writer.writerow([])
    writer.writerow(['총 누적 주행거리 (합산)', '', '', '', '', '', '', f"{total_dist:,.0f} km", '', ''])

    response = Response(output.getvalue(), mimetype='text/csv')
    filename = f"Vehicle_Log_{vehicle.name}_{vehicle.plate_number}_{date.today()}.csv"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response
