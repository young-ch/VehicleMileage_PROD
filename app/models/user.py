"""사용자 및 역할 모델"""
from datetime import datetime, timezone
import bcrypt
from flask_login import UserMixin
from ..extensions import db, login_manager


class Role(db.Model):
    """역할 모델 - admin, manager, viewer"""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    permissions = db.Column(db.JSON, default=dict)

    # 관계
    users = db.relationship('User', backref='role', lazy='dynamic')

    def has_permission(self, permission):
        """특정 권한 보유 여부 확인"""
        return self.permissions.get(permission, False)

    def __repr__(self):
        return f'<Role {self.name}>'


class User(UserMixin, db.Model):
    """사용자 모델"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        """비밀번호를 bcrypt로 해싱하여 저장"""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), salt
        ).decode('utf-8')

    def check_password(self, password):
        """비밀번호 검증"""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def has_permission(self, permission):
        """역할 기반 권한 확인"""
        if self.role:
            return self.role.has_permission(permission)
        return False

    @property
    def is_admin(self):
        return self.role and self.role.name == 'admin'

    @property
    def is_manager(self):
        return self.role and self.role.name in ('admin', 'manager')

    @property
    def is_vehicle_manager(self):
        return self.role and (self.role.name in ('admin', 'manager', 'vehicle_manager') or self.has_permission('vehicle_manage'))

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login 사용자 로더"""
    return User.query.get(int(user_id))
