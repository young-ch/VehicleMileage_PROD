"""Flask 앱 팩토리 - 앱 생성 및 블루프린트 등록"""
from flask import Flask
from .config import config
from .extensions import db, migrate, login_manager, csrf


def create_app(config_name='default'):
    """Flask 앱 생성 팩토리 함수"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # 확장 초기화
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # 모델 임포트 (migrate가 테이블을 인식하도록)
    from .models import user, personnel, jira, audit, vehicle  # noqa: F401

    # 블루프린트 등록
    from .auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .main import main_bp
    app.register_blueprint(main_bp)

    from .personnel import personnel_bp
    app.register_blueprint(personnel_bp, url_prefix='/personnel')

    from .jira import jira_bp
    app.register_blueprint(jira_bp, url_prefix='/jira')

    from .stats import stats_bp
    app.register_blueprint(stats_bp, url_prefix='/stats')

    from .admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from .vehicle import vehicle_bp
    app.register_blueprint(vehicle_bp, url_prefix='/vehicle')

    from .api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # 컨텍스트 프로세서 (템플릿에서 전역으로 사용 가능한 변수)
    @app.context_processor
    def inject_globals():
        return {
            'app_name': 'SMU JIRA 관리 시스템',
        }

    # DB 테이블 자동 생성 (개발 모드)
    with app.app_context():
        db.create_all()
        _seed_initial_data()

    return app


def _seed_initial_data():
    """초기 데이터 시드 (역할, 관리자 계정)"""
    from .models.user import Role, User

    # 기본 역할이 없으면 생성 또는 갱신 동기화
    role_permissions = {
        'admin': {
            'user_manage': True,
            'role_manage': True,
            'personnel_create': True,
            'personnel_edit': True,
            'personnel_delete': True,
            'jira_create': True,
            'jira_edit': True,
            'jira_delete': True,
            'stats_view': True,
            'audit_view': True,
        },
        'manager': {
            'personnel_create': True,
            'personnel_edit': True,
            'personnel_delete': True,
            'jira_create': True,
            'jira_edit': True,
            'jira_delete': True,
            'stats_view': True,
        },
        'viewer': {
            'jira_create': True,
            'jira_edit': True,
            'jira_delete': True,
            'stats_view': True,
        }
    }
    
    for r_name, p_dict in role_permissions.items():
        role = Role.query.filter_by(name=r_name).first()
        if not role:
            role = Role(name=r_name, description=r_name.capitalize(), permissions=p_dict)
            db.session.add(role)
        else:
            # 기존 역할이 있을 경우 최신 기획 권한으로 업데이트 동기화!
            role.permissions = p_dict
            
    db.session.commit()

    # 기본 관리자 계정이 없으면 생성
    if User.query.filter_by(username='admin').first() is None:
        admin_role = Role.query.filter_by(name='admin').first()
        admin_user = User(
            username='admin',
            email='admin@smu.ac.kr',
            role_id=admin_role.id,
            is_active=True,
        )
        admin_user.set_password('admin1234!')  # 초기 비밀번호 (변경 필요)
        db.session.add(admin_user)
        db.session.commit()
