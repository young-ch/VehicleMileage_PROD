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


import re

# 자율형 텍스트 필드 맵
FREE_FIELD_MAP = {
    '소속': 'department',
    '부서': 'department',
    '이름': 'name',
    '성명': 'name',
    '직위': 'position',
    '직급': 'rank',
    '입사일': 'join_date',
    '입사일자': 'join_date',
    'id': 'employee_id',
    '사번': 'employee_id',
    '사원번호': 'employee_id',
}

def parse_unstructured_personnel(text):
    """자율 형식 자유 텍스트 분석기"""
    lines = text.split('\n')
    parsed_data = []
    errors = []
    
    current_status = 'active'
    current_person = {}
    
    def save_person(person):
        if person and (person.get('name') or person.get('employee_id')):
            # 상태 지정
            person['status'] = current_status
            parsed_data.append(person)

    for idx, line in enumerate(lines):
        line_num = idx + 1
        clean_line = line.strip()
        if not clean_line:
            continue
            
        lower_line = clean_line.lower()
        
        # 상태 전환 감지
        if any(k in lower_line for k in ['퇴사', '퇴직', '퇴소']):
            save_person(current_person)
            current_person = {}
            current_status = 'inactive'
            continue
        elif any(k in lower_line for k in ['신규', '신입', '생성', '입사', '등록']):
            save_person(current_person)
            current_person = {}
            current_status = 'active'
            continue
            
        # 새로운 인원 블록 구분선 (대시 또는 등호, 또는 숫자 1번으로 시작하는 행)
        is_new_block = False
        if '===' in clean_line or '---' in clean_line:
            is_new_block = True
        elif clean_line.startswith('1.') or clean_line.startswith('1)'):
            # '소속'이 이미 들어가 있으면 새 블록으로 판단
            if 'department' in current_person or 'name' in current_person:
                is_new_block = True

        if is_new_block:
            save_person(current_person)
            current_person = {}
            continue
            
        # 순번 제거 (예: "1. 소속" -> "소속")
        kv_line = re.sub(r'^\d+[\.\)\-\s]+', '', clean_line).strip()
        
        # 콜론(:) 문자 기준으로 키-값 분리
        if ':' in kv_line:
            parts = kv_line.split(':', 1)
            key = parts[0].strip().replace(' ', '')
            val = parts[1].strip()
            
            # 매핑 시도
            mapped_field = None
            for k, v in FREE_FIELD_MAP.items():
                if k in key or key in k:
                    mapped_field = v
                    break
            
            if mapped_field:
                # 중복 필드가 등장하면 새 인물로 인식하여 저장
                if mapped_field in current_person:
                    save_person(current_person)
                    current_person = {}
                current_person[mapped_field] = val

    save_person(current_person)
    return parsed_data, errors


def parse_personnel_text(text):
    """텍스트를 파싱하여 인원 데이터 리스트로 변환"""
    if not text or not text.strip():
        return {'data': [], 'errors': [{'line': 0, 'message': '입력 데이터가 비어있습니다.'}],
                'columns': [], 'delimiter': '', 'has_header': False}
    
    # 만약 콜론(:)이 있고, '소속'이나 '이름', '성명' 등이 발견되면 자율형 자유 텍스트로 자동 판별
    if ':' in text and any(k in text for k in ['소속', '이름', '성명', '퇴사', '신규']):
        data, errors = parse_unstructured_personnel(text)
        return {
            'data': data,
            'errors': errors,
            'columns': ['employee_id', 'name', 'department', 'position', 'rank', 'join_date', 'status'],
            'delimiter': '자율 텍스트',
            'has_header': False,
        }

    # 기존 TSV/CSV 파싱 로직
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
