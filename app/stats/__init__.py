"""통계 블루프린트"""
from flask import Blueprint

stats_bp = Blueprint('stats', __name__, template_folder='../templates/stats')

from . import routes  # noqa: E402, F401
