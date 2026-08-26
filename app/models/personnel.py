"""인원 및 부서 모델"""
from datetime import datetime, timezone
from ..extensions import db


class Department(db.Model):
    """부서 모델"""
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)

    # 관계
    personnel = db.relationship('Personnel', backref='department', lazy='dynamic')

    def __repr__(self):
        return f'<Department {self.name}>'


class Personnel(db.Model):
    """인원 모델"""
    __tablename__ = 'personnel'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, index=True)
    employee_id = db.Column(db.String(30), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    position = db.Column(db.String(50))  # 직위 (팀장, 파트장 등)
    rank = db.Column(db.String(50))      # 직급 (과장, 대리 등)
    join_date = db.Column(db.Date)
    leave_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='active')  # active, inactive, leave

    # 추적
    registered_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # 관계
    registrar = db.relationship('User', foreign_keys=[registered_by],
                                backref='registered_personnel')

    @property
    def is_active_employee(self):
        return self.status == 'active'

    @property
    def department_name(self):
        return self.department.name if self.department else '미배정'

    def to_dict(self):
        """딕셔너리 변환 (API / 감사 로그용)"""
        return {
            'id': self.id,
            'name': self.name,
            'employee_id': self.employee_id,
            'email': self.email,
            'phone': self.phone,
            'department': self.department_name,
            'position': self.position,
            'rank': self.rank,
            'join_date': str(self.join_date) if self.join_date else None,
            'leave_date': str(self.leave_date) if self.leave_date else None,
            'status': self.status,
        }

    def __repr__(self):
        return f'<Personnel {self.name} ({self.employee_id})>'
