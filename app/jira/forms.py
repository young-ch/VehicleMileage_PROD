"""JIRA 관리 폼"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Length


class JiraIssueForm(FlaskForm):
    """JIRA 이슈 등록/수정 폼"""
    summary = StringField('제목', validators=[
        DataRequired(message='제목을 입력해주세요.'),
        Length(max=500)
    ])
    description = TextAreaField('설명', validators=[Optional()])
    issue_type = SelectField('유형', choices=[
        ('Task', 'Task'),
        ('Bug', 'Bug'),
        ('Story', 'Story'),
        ('Epic', 'Epic'),
        ('Sub-task', 'Sub-task'),
    ])
    priority = SelectField('우선순위', choices=[
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
    ])
    status = SelectField('상태', choices=[
        ('시작전', '시작전'),
        ('진행', '진행'),
        ('보류', '보류'),
        ('완료', '완료'),
    ])
    assignee_id = SelectField('담당자', coerce=int, validators=[Optional()])
    reporter = StringField('보고자', validators=[Optional(), Length(max=100)])
    created_date = DateField('생성일', format='%Y-%m-%d', validators=[Optional()])
    resolved_date = DateField('해결일', format='%Y-%m-%d', validators=[Optional()])
    due_date = DateField('마감일', format='%Y-%m-%d', validators=[Optional()])
    labels = StringField('라벨', validators=[Optional(), Length(max=500)])
    submit = SubmitField('저장')


class JiraPasteForm(FlaskForm):
    """JIRA 텍스트 붙여넣기 폼"""
    paste_data = TextAreaField('데이터 입력', validators=[
        DataRequired(message='데이터를 붙여넣어주세요.')
    ])
    submit = SubmitField('파싱 및 미리보기')


class PersonnelForm(FlaskForm):
    """신규 인원 등록용 폼 (5가지 항목)"""
    name = StringField('성명 *', validators=[
        DataRequired(message='성명을 입력해주세요.'),
        Length(max=100)
    ])
    position = StringField('직위', validators=[Optional(), Length(max=50)])
    join_date = DateField('입사일자', format='%Y-%m-%d', validators=[Optional()])
    employee_id = StringField('사용 아이디 *', validators=[
        DataRequired(message='사용 아이디를 입력해주세요.'),
        Length(max=30)
    ])
    department_name = StringField('지역 / 부서 *', validators=[
        DataRequired(message='지역 또는 부서명을 입력해주세요.'),
        Length(max=100)
    ])
    submit = SubmitField('저장')


class RetireForm(FlaskForm):
    """이름만 입력하여 퇴사 처리하는 폼"""
    name = StringField('퇴직자 성함 *', validators=[
        DataRequired(message='퇴직 처리할 인원의 이름을 입력해주세요.'),
        Length(max=100)
    ])
    leave_date = DateField('퇴사일자', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('퇴사 처리 실행')
