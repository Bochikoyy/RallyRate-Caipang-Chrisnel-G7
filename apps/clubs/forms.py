from django import forms

from .models import Club


class ClubForm(forms.ModelForm):
    class Meta:
        model = Club
        fields = ("name", "home_court", "description", "is_public")
        widgets = {
            "name": forms.TextInput(attrs={"class": "field-input", "placeholder": "e.g., Cebu Smashers Pickleball Club"}),
            "home_court": forms.TextInput(attrs={"class": "field-input", "placeholder": "e.g., Metrosports Lahug · Courts 1–4"}),
            "description": forms.Textarea(
                attrs={
                    "class": "field-input",
                    "rows": 3,
                    "placeholder": "Share club schedule, skill levels welcome, and court etiquette.",
                }
            ),
            "is_public": forms.CheckboxInput(),
        }
        labels = {
            "name": "Club name",
            "home_court": "Primary court / venue",
            "description": "About this club",
            "is_public": "Public club (visible in directory & open for instant join)",
        }

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if len(name) < 3:
            raise forms.ValidationError("Club name must be at least 3 characters.")
        return name

    def clean_home_court(self):
        court = (self.cleaned_data.get("home_court") or "").strip()
        if not court:
            raise forms.ValidationError("Please enter the club's primary court or venue.")
        return court


class JoinClubCodeForm(forms.Form):
    join_code = forms.CharField(
        label="Club invite code",
        max_length=16,
        widget=forms.TextInput(
            attrs={
                "class": "field-input",
                "placeholder": "e.g., RR-7K4M9P",
                "autocomplete": "off",
            }
        ),
    )

    def clean_join_code(self):
        code = (self.cleaned_data.get("join_code") or "").strip().upper()
        if not code:
            raise forms.ValidationError("Enter a club invite code.")
        return code
