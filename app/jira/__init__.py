"""JIRA 관리 블루프린트"""
from flask import Blueprint

jira_bp = Blueprint('jira', __name__, template_folder='../templates/jira')

from . import routes  # noqa: E402, F401
