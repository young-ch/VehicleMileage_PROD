"""법인차량 및 운행일지 모델"""
from datetime import datetime, timezone
from ..extensions import db


class Vehicle(db.Model):
    """법인차량 모델"""
    __tablename__ = 'vehicles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)          # 차종 (예: 스타리아, 카니발, 니로)
    plate_number = db.Column(db.String(50), nullable=False)   # 차량번호 (예: 160하8962)
    fuel_type = db.Column(db.String(50), default='경유')       # 유종 (경유, 휘발유, 전기 등)
    notice = db.Column(db.String(500), default='사용후 반드시 본관앞 주차!! 연료 50% 이하시 주유!!')
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    logs = db.relationship('VehicleLog', backref='vehicle', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'plate_number': self.plate_number,
            'fuel_type': self.fuel_type,
            'notice': self.notice,
        }


class VehicleLog(db.Model):
    """법인차량 운행일지 기록 모델"""
    __tablename__ = 'vehicle_logs'

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    
    start_time = db.Column(db.String(50))     # 시작시간 (날짜, 시간) e.g. "2026-08-07 11:00 AM"
    end_time = db.Column(db.String(50))       # 종료시간 (날짜, 시간) e.g. "2026-08-07 9:00 PM"
    
    department = db.Column(db.String(100))    # 부서 (예: 국제협력국, 기획경영국, 행정지원국)
    applicant = db.Column(db.String(50))      # 신청자 (성명)
    driver = db.Column(db.String(50))         # 운전자 (성명)
    
    start_distance = db.Column(db.Float, default=0.0)  # 주행 전 계기판 거리 (km)
    end_distance = db.Column(db.Float, default=0.0)    # 주행 후 계기판 거리 (km) = 주행전 + 주행거리
    distance = db.Column(db.Float, default=0.0)        # 주행거리 (km)
    
    purpose = db.Column(db.Text)              # 용도 / 구체적 사유
    notes = db.Column(db.Text)                # 비고 (충전필요, 사고여부 등)
    
    registered_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    registrar = db.relationship('User', foreign_keys=[registered_by])
