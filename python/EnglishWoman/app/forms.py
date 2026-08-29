# forms.py
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class UserResponseForm(forms.Form):
    question_id = forms.IntegerField(widget=forms.HiddenInput)
    selected_option = forms.IntegerField(min_value=1, max_value=4)



class RegisterForm(forms.ModelForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'نام کاربری', 'class': 'form-control'}),
        label="نام کاربری"
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'ایمیل', 'class': 'form-control'}),
        label="ایمیل"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'رمز عبور', 'class': 'form-control'}),
        label="رمز عبور"
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'تکرار رمز عبور', 'class': 'form-control'}),
        label="تکرار رمز عبور"
    )

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise ValidationError("رمز عبور و تکرار آن یکسان نیستند.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])  # هش کردن رمز عبور
        if commit:
            user.save()
        return user

class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'نام کاربری', 'class': 'form-control'}),
        label="نام کاربری"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'رمز عبور', 'class': 'form-control'}),
        label="رمز عبور"
    )



