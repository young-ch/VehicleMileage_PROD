"""인원 텍스트 붙여넣기 파서

지원 포맷:
- 탭 구분 (TSV) - 엑셀에서 복사시 기본
- 쉼표 구분 (CSV)
- 파이프 구분 (|)

기본 컬럼 순서:
사번 | 이름 | 부서 | 직급 | 직위 | 이메일 | 전화번호 | 입사일
"""
import csv
import io


# 컬럼 매핑 (헤더 → 필드명)
COLUMN_MAP = {
    '사번': 'employee_id',
    '사원번호': 'employee_id',
    'employee_id': 'employee_id',
    '이름': 'name',
    '성명': 'name',
    'name': 'name',
    '부서': 'department',
    'department': 'department',
    '직급': 'rank',
    'rank': 'rank',
    '직위': 'position',
    'position': 'position',
    '이메일': 'email',
    'email': 'email',
    '전화번호': 'phone',
    '전화': 'phone',
    '연락처': 'phone',
    'phone': 'phone',
    '입사일': 'join_date',
    '입사일자': 'join_date',
    'join_date': 'join_date',
    '상태': 'status',
    'status': 'status',
}

# 기본 컬럼 순서 (헤더 없을 때)
DEFAULT_COLUMNS = ['employee_id', 'name', 'department', 'rank', 'position', 'email', 'phone', 'join_date']


def detect_delimiter(text):
    """구분자 자동 감지"""
    first_line = text.strip().split('\n')[0]
    
    # 탭이 있으면 TSV
    if '\t' in first_line:
        return '\t'
    # 쉼표 개수가 많으면 CSV
    if first_line.count(',') >= 2:
        return ','
    # 파이프가 있으면 파이프 구분
    if '|' in first_line:
        return '|'
    # 기본은 탭
    return '\t'


def detect_header(fields, delimiter):
    """첫 줄이 헤더인지 자동 판별"""
    # 첫 줄의 셀들이 컬럼 매핑에 있으면 헤더로 판단
    normalized = [f.strip().lower() for f in fields]
    matched = sum(1 for f in normalized if f in [k.lower() for k in COLUMN_MAP.keys()])
    return matched >= 2  # 2개 이상 매칭되면 헤더


def parse_personnel_text(text):
    """텍스트를 파싱하여 인원 데이터 리스트로 변환
    
    Args:
        text: 붙여넣기된 텍스트
        
    Returns:
        dict: {
            'data': [{'employee_id': ..., 'name': ..., ...}, ...],
            'errors': [{'line': 1, 'message': '...'}, ...],
            'columns': ['employee_id', 'name', ...],
            'delimiter': '\t',
            'has_header': True,
        }
    """
    if not text or not text.strip():
        return {'data': [], 'errors': [{'line': 0, 'message': '입력 데이터가 비어있습니다.'}],
                'columns': [], 'delimiter': '', 'has_header': False}
    
    lines = text.strip().split('\n')
    delimiter = detect_delimiter(text)
    
    # 첫 줄 파싱
    first_fields = lines[0].split(delimiter) if delimiter != ',' else next(csv.reader([lines[0]]))
    first_fields = [f.strip() for f in first_fields]
    
    has_header = detect_header(first_fields, delimiter)
    
    # 컬럼 매핑 결정
    if has_header:
        columns = []
        for field in first_fields:
            field_lower = field.strip().lower()
            mapped = None
            for key, value in COLUMN_MAP.items():
                if key.lower() == field_lower:
                    mapped = value
                    break
            columns.append(mapped or field.strip())
        data_lines = lines[1:]
    else:
        columns = DEFAULT_COLUMNS[:len(first_fields)]
        data_lines = lines
    
    # 데이터 파싱
    parsed_data = []
    errors = []
    
    for idx, line in enumerate(data_lines):
        line = line.strip()
        if not line:
            continue
        
        line_num = idx + (2 if has_header else 1)
        
        try:
            if delimiter == ',':
                fields = next(csv.reader([line]))
            else:
                fields = line.split(delimiter)
            
            fields = [f.strip() for f in fields]
            
            if len(fields) < 2:  # 최소 사번 + 이름
                errors.append({'line': line_num, 'message': f'필드 수 부족 ({len(fields)}개)'})
                continue
            
            row = {}
            for i, col in enumerate(columns):
                if i < len(fields):
                    row[col] = fields[i] if fields[i] else None
                else:
                    row[col] = None
            
            # 필수 필드 체크
            if not row.get('employee_id') and not row.get('name'):
                errors.append({'line': line_num, 'message': '사번 또는 이름이 누락되었습니다.'})
                continue
            
            parsed_data.append(row)
            
        except Exception as e:
            errors.append({'line': line_num, 'message': str(e)})
    
    return {
        'data': parsed_data,
        'errors': errors,
        'columns': columns,
        'delimiter': delimiter,
        'has_header': has_header,
    }
