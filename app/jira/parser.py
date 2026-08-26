"""JIRA 텍스트 붙여넣기 파서

지원 포맷:
- 탭 구분 (TSV) - 엑셀에서 복사시 기본
- 쉼표 구분 (CSV)

기본 컬럼 순서:
JIRA Key | Summary | Type | Priority | Status | Assignee | Reporter | Created | Sprint
"""
import csv
import io


COLUMN_MAP = {
    'jira_key': 'jira_key',
    'key': 'jira_key',
    '키': 'jira_key',
    'jira키': 'jira_key',
    '이슈키': 'jira_key',
    'issue key': 'jira_key',
    'summary': 'summary',
    '제목': 'summary',
    '요약': 'summary',
    'type': 'issue_type',
    'issue type': 'issue_type',
    '유형': 'issue_type',
    '이슈유형': 'issue_type',
    'priority': 'priority',
    '우선순위': 'priority',
    'status': 'status',
    '상태': 'status',
    'assignee': 'assignee',
    '담당자': 'assignee',
    'reporter': 'reporter',
    '보고자': 'reporter',
    '등록자': 'reporter',
    'created': 'created_date',
    '생성일': 'created_date',
    '등록일': 'created_date',
    'resolved': 'resolved_date',
    '해결일': 'resolved_date',
    '완료일': 'resolved_date',
    'due date': 'due_date',
    '마감일': 'due_date',
    'sprint': 'sprint',
    '스프린트': 'sprint',
    'epic': 'epic',
    '에픽': 'epic',
    'labels': 'labels',
    '라벨': 'labels',
    'description': 'description',
    '설명': 'description',
    '내용': 'description',
}

DEFAULT_COLUMNS = ['jira_key', 'summary', 'issue_type', 'priority', 'status',
                   'assignee', 'reporter', 'created_date', 'sprint']


def detect_delimiter(text):
    """구분자 자동 감지"""
    first_line = text.strip().split('\n')[0]
    if '\t' in first_line:
        return '\t'
    if first_line.count(',') >= 2:
        return ','
    if '|' in first_line:
        return '|'
    return '\t'


def detect_header(fields):
    """첫 줄이 헤더인지 판별"""
    normalized = [f.strip().lower() for f in fields]
    matched = sum(1 for f in normalized if f in [k.lower() for k in COLUMN_MAP.keys()])
    return matched >= 2


def parse_jira_text(text):
    """텍스트를 파싱하여 JIRA 이슈 데이터 리스트로 변환
    
    Returns:
        dict: {
            'data': [{...}, ...],
            'errors': [{'line': N, 'message': '...'}, ...],
            'columns': [...],
            'delimiter': '\t',
            'has_header': True,
        }
    """
    if not text or not text.strip():
        return {'data': [], 'errors': [{'line': 0, 'message': '입력 데이터가 비어있습니다.'}],
                'columns': [], 'delimiter': '', 'has_header': False}
    
    lines = text.strip().split('\n')
    delimiter = detect_delimiter(text)
    
    first_fields = lines[0].split(delimiter) if delimiter != ',' else next(csv.reader([lines[0]]))
    first_fields = [f.strip() for f in first_fields]
    
    has_header = detect_header(first_fields)
    
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
            
            if len(fields) < 2:
                errors.append({'line': line_num, 'message': f'필드 수 부족 ({len(fields)}개)'})
                continue
            
            row = {}
            for i, col in enumerate(columns):
                if i < len(fields):
                    row[col] = fields[i] if fields[i] else None
                else:
                    row[col] = None
            
            if not row.get('jira_key') and not row.get('summary'):
                errors.append({'line': line_num, 'message': 'JIRA Key 또는 제목이 누락되었습니다.'})
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
