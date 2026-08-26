"""REST API 라우트 (추후 확장용)"""
from flask import jsonify
from flask_login import login_required
from . import api_bp


@api_bp.route('/health')
def health():
    """헬스체크 엔드포인트"""
    return jsonify({'status': 'ok', 'service': 'SMU JIRA Management System'})
