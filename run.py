"""SMU JIRA 관리 시스템 - 앱 실행 엔트리포인트"""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=app.config.get('DEBUG', False)
    )
