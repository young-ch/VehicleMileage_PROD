"""메인 블루프린트 (대시보드)"""
from flask import Blueprint

main_bp = Blueprint('main', __name__, template_folder='../templates/main')

from . import routes  # noqa: E402, F401
