from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
import re

class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="メールアドレス", required=True)

    class Meta:
        model = User
        fields = ("username", "email")
    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if len(password) < 8:
            raise forms.ValidationError("パスワードは8文字以上で入力してください。")
        if not re.search(r'[a-zA-Z]', password) or not re.search(r'[0-9]', password):
            raise forms.ValidationError("パスワードには英字と数字の両方を含めてください。")
        return password

class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="メールアドレス", widget=forms.EmailInput(attrs={'autofocus': True}))

    def clean_username(self):
        email = self.cleaned_data.get('username')
        try:
            return User.objects.get(email=email).username
        except User.DoesNotExist:
            raise forms.ValidationError("このメールアドレスで登録されたユーザーは見つかりません。")