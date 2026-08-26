"""인원 관리 폼"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length


class PersonnelForm(FlaskForm):
    """신규 인원 등록용 폼 (5가지 항목)"""
    name = StringField('성명 *', validators=[
        DataRequired(message='성명을 입력해주세요.'),
        Length(max=50)
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
    """퇴직자 직접 등록 및 퇴사 처리 폼"""
    name = StringField('퇴직자 성함 *', validators=[
        DataRequired(message='퇴직자 성함을 입력해주세요.'),
        Length(max=50)
    ])
    leave_date = DateField('퇴사일자', format='%Y-%m-%d', validators=[Optional()])
    department_name = StringField('지역 / 부서', validators=[Optional(), Length(max=100)])
    position = StringField('직위', validators=[Optional(), Length(max=50)])
    employee_id = StringField('사용 아이디', validators=[Optional(), Length(max=30)])
    submit = SubmitField('퇴직자 등록 실행')
