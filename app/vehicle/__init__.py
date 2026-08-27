from flask import Blueprint

vehicle_bp = Blueprint('vehicle', __name__)

from . import routes  # noqa: F401
