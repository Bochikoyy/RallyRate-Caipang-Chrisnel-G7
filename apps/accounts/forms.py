from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import User


def style_fields(form):
    for field in form.fields.values():
        field.widget.attrs["class"] = "field-input"
        field.widget.attrs.setdefault("autocomplete", "on")


class SignUpForm(UserCreationForm):
    full_name = forms.CharField(
        label="Full name",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "e.g., Maya Chen"}),
    )
    email = forms.EmailField(
        label="Email address",
        required=True,
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}),
    )

    class Meta:
        model = User
        fields = ("full_name", "email", "preferred_paddle", "home_court")
        widgets = {
            "preferred_paddle": forms.TextInput(attrs={"placeholder": "e.g., Selkirk LUXX Control"}),
            "home_court": forms.TextInput(attrs={"placeholder": "e.g., Riverside Pickleball Club"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)
        self.order_fields(["full_name", "email", "password1", "password2", "preferred_paddle", "home_court"])
        self.fields["password1"].widget.attrs.update({"autocomplete": "new-password", "placeholder": "At least 8 characters"})
        self.fields["password2"].widget.attrs.update({"autocomplete": "new-password", "placeholder": "Re-enter password"})

    def clean_full_name(self):
        name = (self.cleaned_data.get("full_name") or "").strip()
        if not name:
            raise forms.ValidationError("Please enter your full name.")
        return name

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Please enter your email address.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try signing in instead.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        parts = self.cleaned_data["full_name"].strip().split(maxsplit=1)
        user.username = User.objects.username_for_email(self.cleaned_data["email"])
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
        user.role = User.Role.PLAYER
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
    full_name = forms.CharField(
        label="Full name",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Your full name"}),
    )

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
        self.fields["first_name"].required = False
        self.fields["last_name"].required = False
        if self.instance and self.instance.pk:
            combined = f"{self.instance.first_name} {self.instance.last_name}".strip()
            self.fields["full_name"].initial = combined
        style_fields(self)

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            if self.instance and self.instance.email:
                raise forms.ValidationError("Email address is required so you can sign in.")
            return None
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Another account is already using this email address.")
        return email

    def clean(self):
        cleaned = super().clean()
        full_name = (cleaned.get("full_name") or "").strip()
        first_name = (cleaned.get("first_name") or "").strip()
        last_name = (cleaned.get("last_name") or "").strip()

        if "full_name" in self.data:
            if not full_name:
                self.add_error("full_name", "Please enter your full name.")
            else:
                parts = full_name.split(maxsplit=1)
                cleaned["first_name"] = parts[0]
                cleaned["last_name"] = parts[1] if len(parts) > 1 else ""
        elif first_name:
            cleaned["first_name"] = first_name
            cleaned["last_name"] = last_name
        elif not (self.instance and self.instance.is_superuser):
            self.add_error("full_name", "Please enter your full name.")
        return cleaned
