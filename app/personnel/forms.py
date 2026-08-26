"""인원 관리 폼"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length


class PersonnelForm(FlaskForm):
    """인원 등록/수정 폼"""
    employee_id = StringField('사번', validators=[
        DataRequired(message='사번을 입력해주세요.'),
        Length(max=30)
    ])
    name = StringField('이름', validators=[
        DataRequired(message='이름을 입력해주세요.'),
        Length(max=50)
    ])
    email = StringField('이메일', validators=[Optional(), Email()])
    phone = StringField('전화번호', validators=[Optional(), Length(max=20)])
    department_id = SelectField('부서', coerce=int, validators=[Optional()])
    position = StringField('직위', validators=[Optional(), Length(max=50)])
    rank = StringField('직급', validators=[Optional(), Length(max=50)])
    join_date = DateField('입사일', format='%Y-%m-%d', validators=[Optional()])
    leave_date = DateField('퇴사일', format='%Y-%m-%d', validators=[Optional()])
    status = SelectField('상태', choices=[
        ('active', '재직'),
        ('inactive', '퇴직'),
        ('leave', '휴직'),
    ])
    submit = SubmitField('저장')


class PersonnelPasteForm(FlaskForm):
    """인원 텍스트 붙여넣기 폼"""
    paste_data = TextAreaField('데이터 입력', validators=[
        DataRequired(message='데이터를 붙여넣어주세요.')
    ])
    submit = SubmitField('파싱 및 미리보기')
