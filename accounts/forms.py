from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import User


def style_fields(form):
    for field in form.fields.values():
        field.widget.attrs["class"] = "field-input"
        field.widget.attrs.setdefault("autocomplete", "on")


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "preferred_paddle", "home_court")
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "preferred_paddle": forms.TextInput(attrs={"placeholder": "Optional"}),
            "home_court": forms.TextInput(attrs={"placeholder": "Optional"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
        self.fields["password1"].widget.attrs.update({"autocomplete": "new-password"})
        self.fields["password2"].widget.attrs.update({"autocomplete": "new-password"})

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"class": "field-input", "autocomplete": "email", "autofocus": True}))
    password = forms.CharField(label="Password", strip=False, widget=forms.PasswordInput(attrs={"class": "field-input", "autocomplete": "current-password"}))


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number", "preferred_paddle", "home_court")
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone_number": forms.TelInput(attrs={"autocomplete": "tel", "placeholder": "Optional"}),
            "preferred_paddle": forms.TextInput(attrs={"placeholder": "Optional"}),
            "home_court": forms.TextInput(attrs={"placeholder": "Optional"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
