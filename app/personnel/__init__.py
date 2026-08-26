"""인원 관리 블루프린트"""
from flask import Blueprint

personnel_bp = Blueprint('personnel', __name__, template_folder='../templates/personnel')

from . import routes  # noqa: E402, F401
