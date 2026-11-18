from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import User


def style_fields(form):
    for field in form.fields.values():
        field.widget.attrs["class"] = "field-input"
        field.widget.attrs.setdefault("autocomplete", "on")


class SignUpForm(UserCreationForm):
    full_name = forms.CharField(label="Full name", max_length=150, widget=forms.TextInput(attrs={"autocomplete": "name"}))

    class Meta:
        model = User
        fields = ("full_name", "email", "role", "preferred_paddle", "home_court")
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "preferred_paddle": forms.TextInput(attrs={"placeholder": "Optional"}),
            "home_court": forms.TextInput(attrs={"placeholder": "Optional"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
        self.fields["role"].initial = User.Role.PLAYER
        self.order_fields(["full_name", "email", "password1", "password2", "role", "preferred_paddle", "home_court"])
        self.fields["password1"].widget.attrs.update({"autocomplete": "new-password"})
        self.fields["password2"].widget.attrs.update({"autocomplete": "new-password"})

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def save(self, commit=True):
        user = super().save(commit=False)
        parts = self.cleaned_data["full_name"].strip().split(maxsplit=1)
        user.username = User.objects.username_for_email(self.cleaned_data["email"])
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
        if commit:
            user.save()
        return user


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"class": "field-input", "autocomplete": "email", "autofocus": True}))
    password = forms.CharField(label="Password", strip=False, widget=forms.PasswordInput(attrs={"class": "field-input", "autocomplete": "current-password"}))

    def clean_username(self):
        # Signup stores emails in lowercase; normalize login input the same way.
        return self.cleaned_data["username"].strip().lower()


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number", "preferred_paddle", "home_court")
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone_number": forms.TelInput(attrs={"autocomplete": "tel", "placeholder": "Optional"}),
            "preferred_paddle": forms.TextInput(attrs={"placeholder": "Optional"}),
            "home_court": forms.TextInput(attrs={"placeholder": "Optional"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
