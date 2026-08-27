"""모델 패키지 - 모든 모델을 여기서 임포트"""
from .user import User, Role
from .personnel import Personnel, Department
from .jira import JiraIssue, IssueComment
from .audit import AuditLog, PasteHistory
from .vehicle import Vehicle, VehicleLog

__all__ = [
    'User', 'Role',
    'Personnel', 'Department',
    'JiraIssue', 'IssueComment',
    'AuditLog', 'PasteHistory',
    'Vehicle', 'VehicleLog',
]
