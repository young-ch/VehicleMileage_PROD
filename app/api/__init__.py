"""REST API 블루프린트 (추후 확장용)"""
from flask import Blueprint

api_bp = Blueprint('api', __name__)

from . import routes  # noqa: E402, F401
