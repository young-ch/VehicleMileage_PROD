# 1. 파이썬 환경 가져오기
FROM python:3.9-slim

# 2. 도커 안에서 작업할 기본 폴더 지정
WORKDIR /app

# 3. 라이브러리 목록 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 나머지 소스 코드 복사
COPY . .

# 5. 플라스크(Flask) 포트 노출
EXPOSE 5000

# 6. 프로그램 실행
CMD ["python", "run.py"]
