"""인증 폼"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from ..models.user import User
import re


class LoginForm(FlaskForm):
    """로그인 폼"""
    username = StringField('사용자명', validators=[
        DataRequired(message='사용자명을 입력해주세요.')
    ])
    password = PasswordField('비밀번호', validators=[
        DataRequired(message='비밀번호를 입력해주세요.')
    ])
    remember_me = BooleanField('로그인 상태 유지')
    submit = SubmitField('로그인')


class RegisterForm(FlaskForm):
    """회원가입 폼"""
    username = StringField('사용자명', validators=[
        DataRequired(message='사용자명을 입력해주세요.'),
        Length(min=3, max=80, message='사용자명은 3~80자여야 합니다.')
    ])
    email = StringField('이메일', validators=[
        DataRequired(message='이메일을 입력해주세요.'),
        Email(message='올바른 이메일 형식이 아닙니다.')
    ])
    password = PasswordField('비밀번호', validators=[
        DataRequired(message='비밀번호를 입력해주세요.'),
        Length(min=8, message='비밀번호는 최소 8자 이상이어야 합니다.')
    ])
    password_confirm = PasswordField('비밀번호 확인', validators=[
        DataRequired(message='비밀번호를 다시 입력해주세요.'),
        EqualTo('password', message='비밀번호가 일치하지 않습니다.')
    ])
    submit = SubmitField('회원가입')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('이미 사용 중인 사용자명입니다.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('이미 등록된 이메일입니다.')

    def validate_password(self, field):
        """비밀번호 정책: 영문 + 숫자 + 특수문자 포함"""
        password = field.data
        if not re.search(r'[A-Za-z]', password):
            raise ValidationError('비밀번호에 영문자를 포함해야 합니다.')
        if not re.search(r'[0-9]', password):
            raise ValidationError('비밀번호에 숫자를 포함해야 합니다.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('비밀번호에 특수문자를 포함해야 합니다.')


class ChangePasswordForm(FlaskForm):
    """비밀번호 변경 폼"""
    current_password = PasswordField('현재 비밀번호 *', validators=[
        DataRequired(message='현재 비밀번호를 입력해주세요.')
    ])
    new_password = PasswordField('새 비밀번호 *', validators=[
        DataRequired(message='새 비밀번호를 입력해주세요.'),
        Length(min=8, message='비밀번호는 최소 8자 이상이어야 합니다.')
    ])
    confirm_password = PasswordField('새 비밀번호 확인 *', validators=[
        DataRequired(message='새 비밀번호 확인을 입력해주세요.'),
        EqualTo('new_password', message='비밀번호가 일치하지 않습니다.')
    ])
    submit = SubmitField('비밀번호 변경')

    def validate_new_password(self, field):
        """비밀번호 정책 검증"""
        password = field.data
        if not re.search(r'[A-Za-z]', password):
            raise ValidationError('비밀번호에 영문자를 포함해야 합니다.')
        if not re.search(r'[0-9]', password):
            raise ValidationError('비밀번호에 숫자를 포함해야 합니다.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('비밀번호에 특수문자를 포함해야 합니다.')


class AdminUserCreateForm(FlaskForm):
    """관리자용 신규 사용자 생성 폼"""
    username = StringField('사용자명 *', validators=[
        DataRequired(message='사용자명을 입력해주세요.'),
        Length(min=3, max=80, message='사용자명은 3~80자여야 합니다.')
    ])
    email = StringField('이메일 *', validators=[
        DataRequired(message='이메일을 입력해주세요.'),
        Email(message='올바른 이메일 형식이 아닙니다.')
    ])
    role_id = SelectField('역할 *', coerce=int, validators=[
        DataRequired(message='역할을 선택해주세요.')
    ])
    password = PasswordField('초기 비밀번호 *', validators=[
        DataRequired(message='초기 비밀번호를 입력해주세요.'),
        Length(min=8, message='비밀번호는 최소 8자 이상이어야 합니다.')
    ])
    submit = SubmitField('사용자 생성')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('이미 사용 중인 사용자명입니다.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('이미 등록된 이메일입니다.')

    def validate_password(self, field):
        password = field.data
        if not re.search(r'[A-Za-z]', password):
            raise ValidationError('비밀번호에 영문자를 포함해야 합니다.')
        if not re.search(r'[0-9]', password):
            raise ValidationError('비밀번호에 숫자를 포함해야 합니다.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('비밀번호에 특수문자를 포함해야 합니다.')
