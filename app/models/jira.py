"""JIRA 이슈 및 코멘트 모델"""
from datetime import datetime, timezone
from ..extensions import db


class JiraIssue(db.Model):
    """JIRA 이슈 모델"""
    __tablename__ = 'jira_issues'

    id = db.Column(db.Integer, primary_key=True)
    jira_key = db.Column(db.String(30), unique=True, nullable=False, index=True)  # e.g. SMU-123
    summary = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    issue_type = db.Column(db.String(30))     # Bug, Task, Story, Epic
    priority = db.Column(db.String(20))        # Critical, High, Medium, Low
    status = db.Column(db.String(30))          # Open, In Progress, Resolved, Closed
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    reporter = db.Column(db.String(100))
    created_date = db.Column(db.Date)          # JIRA에서의 생성일
    resolved_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    sprint = db.Column(db.String(100))
    epic = db.Column(db.String(200))
    labels = db.Column(db.String(500))         # 쉼표 구분

    # 시스템 추적
    registered_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # 관계
    registrar = db.relationship('User', foreign_keys=[registered_by],
                                backref='registered_issues')
    assignee = db.relationship('User', foreign_keys=[assignee_id],
                               backref='assigned_issues')
    comments = db.relationship('IssueComment', backref='issue',
                               lazy='dynamic', cascade='all, delete-orphan')

    @property
    def assignee_name(self):
        return self.assignee.username if self.assignee else '미배정'

    def to_dict(self):
        """딕셔너리 변환"""
        return {
            'id': self.id,
            'jira_key': self.jira_key,
            'summary': self.summary,
            'issue_type': self.issue_type,
            'priority': self.priority,
            'status': self.status,
            'assignee': self.assignee_name,
            'reporter': self.reporter,
            'created_date': str(self.created_date) if self.created_date else None,
            'resolved_date': str(self.resolved_date) if self.resolved_date else None,
            'sprint': self.sprint,
            'epic': self.epic,
        }

    def __repr__(self):
        return f'<JiraIssue {self.jira_key}>'


class IssueComment(db.Model):
    """이슈 코멘트 모델"""
    __tablename__ = 'issue_comments'

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('jira_issues.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # 관계
    author = db.relationship('User', backref='comments')

    def __repr__(self):
        return f'<IssueComment {self.id} on {self.issue_id}>'
