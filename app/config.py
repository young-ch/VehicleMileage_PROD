"""환경별 설정 클래스"""
import os
from datetime import timedelta


class BaseConfig:
    """기본 설정"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 세션 설정
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.getenv('SESSION_LIFETIME_MINUTES', 30))
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # WTF CSRF
    WTF_CSRF_ENABLED = True
    
    # 페이지네이션
    ITEMS_PER_PAGE = 20


class DevelopmentConfig(BaseConfig):
    """개발 환경 설정"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///smu_jira_dev.db'  # 개발시 SQLite 사용 가능
    )


class ProductionConfig(BaseConfig):
    """프로덕션 환경 설정"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SESSION_COOKIE_SECURE = True  # HTTPS only


class TestingConfig(BaseConfig):
    """테스트 환경 설정"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
