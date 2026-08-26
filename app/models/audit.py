"""감사 로그 및 붙여넣기 이력 모델"""
from datetime import datetime, timezone
from ..extensions import db


class AuditLog(db.Model):
    """감사 로그 - 모든 데이터 변경 이력 추적"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(20), nullable=False)  # CREATE, UPDATE, DELETE
    target_table = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer)
    old_values = db.Column(db.JSON)
    new_values = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # 관계
    user = db.relationship('User', backref='audit_logs')

    def __repr__(self):
        return f'<AuditLog {self.action} {self.target_table}:{self.target_id}>'


class PasteHistory(db.Model):
    """텍스트 붙여넣기 이력"""
    __tablename__ = 'paste_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    paste_type = db.Column(db.String(20), nullable=False)  # personnel, jira
    raw_data = db.Column(db.Text)
    success_count = db.Column(db.Integer, default=0)
    fail_count = db.Column(db.Integer, default=0)
    error_details = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # 관계
    user = db.relationship('User', backref='paste_history')

    def __repr__(self):
        return f'<PasteHistory {self.paste_type} +{self.success_count}/-{self.fail_count}>'
