import hashlib
import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import FreelancerProfile, HirerAccessCode, Job, User


class RoleLoginForm(AuthenticationForm):
    def __init__(self, *args, role=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if self.role and user.role != self.role:
            raise self.get_invalid_login_error()


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    location = forms.CharField(
        max_length=100, label="Town or neighbourhood",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Westlands, Nairobi"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "email", "location", "username")


class FreelancerRegistrationForm(RegistrationForm):
    field_order = [
        "first_name", "last_name", "email", "location", "username", "skills", "available",
        "document_type", "document_number", "password1", "password2",
    ]
    skills = forms.CharField(
        max_length=240, widget=forms.TextInput(attrs={"placeholder": "e.g. Carpentry, furniture repair"})
    )
    available = forms.BooleanField(required=False, initial=True, label="Available for work")
    document_type = forms.ChoiceField(
        choices=[("", "Select document type"), *FreelancerProfile.DocumentType.choices]
    )
    document_number = forms.CharField(
        label="National ID or passport number",
        max_length=24,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
        help_text="Use a fictional number for the class demonstration.",
    )

    def clean_document_number(self):
        number = self.cleaned_data["document_number"].upper()
        if not re.fullmatch(r"[A-Z0-9]{5,24}", number):
            raise forms.ValidationError("Enter 5 to 24 letters or digits.")
        return number


class HirerRegistrationForm(RegistrationForm):
    field_order = [
        "first_name", "last_name", "email", "location", "username", "requirement_id",
        "password1", "password2",
    ]
    requirement_id = forms.CharField(
        label="Hirer requirement ID",
        max_length=32,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
        help_text="Enter the one-time ID issued by a KaziLink administrator.",
    )

    def clean_requirement_id(self):
        code = self.cleaned_data["requirement_id"].upper()
        if re.fullmatch(r"[0-9A-F]{32}", code):
            digest = hashlib.sha256(code.encode()).hexdigest()
            if HirerAccessCode.objects.filter(digest=digest, redeemed_at__isnull=True).exists():
                return digest
        raise forms.ValidationError("Enter a valid, unused hirer requirement ID.")


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ("title", "description", "location", "duration", "pay", "expectations")
        labels = {"pay": "Pay (KES)", "expectations": "Requirements and what to expect"}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "expectations": forms.Textarea(attrs={"rows": 3}),
            "duration": forms.TextInput(attrs={"placeholder": "e.g. 4 hours"}),
        }
