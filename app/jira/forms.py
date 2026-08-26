"""JIRA 관리 폼"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Length


class JiraIssueForm(FlaskForm):
    """JIRA 이슈 등록/수정 폼"""
    jira_key = StringField('JIRA Key (미입력 시 자동 생성)', validators=[
        Optional(),
        Length(max=30)
    ])
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
