import hashlib
import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from .models import FreelancerProfile, HirerAccessCode, Job, User


class RoleLoginForm(AuthenticationForm):
    remember_me = forms.BooleanField(
        required=False,
        label="Keep me signed in",
        help_text="Select this on a device you trust.",
    )

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.pop("autofocus", None)


class FreelancerDocumentNumberField(forms.CharField):
    def __init__(self, **kwargs):
        super().__init__(
            label="National ID or passport number",
            max_length=24,
            widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
            help_text="Use a fictional number for the class demonstration.",
            **kwargs,
        )

    def clean(self, value):
        number = super().clean(value).upper()
        if number and not re.fullmatch(r"[A-Z0-9]{5,24}", number):
            raise forms.ValidationError("Enter 5 to 24 letters or digits.")
        return number


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
    document_number = FreelancerDocumentNumberField()


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


class JobApplicationForm(forms.Form):
    note = forms.CharField(
        required=False, max_length=1500, label="Note to the hirer",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    resume = forms.FileField(
        label="Résumé (PDF)", help_text="Up to 5 MB. Shared privately with the hirer.",
        validators=[FileExtensionValidator(["pdf"])],
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,application/pdf"}),
    )

    def clean_resume(self):
        resume = self.cleaned_data["resume"]
        if resume.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Choose a PDF no larger than 5 MB.")
        if resume.read(5) != b"%PDF-":
            raise forms.ValidationError("Upload a PDF file.")
        resume.seek(0)
        return resume


class CandidateInvitationForm(forms.Form):
    invitation_note = forms.CharField(
        required=False, max_length=1500, label="Message to the candidate",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    interview_at = forms.DateTimeField(
        required=False, label="Interview date and time",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="Kenya time (EAT). Leave blank to arrange the interview later.",
    )
    interview_details = forms.CharField(
        required=False, max_length=350, label="Interview location or meeting details",
    )

    def clean(self):
        data = super().clean()
        interview_at = data.get("interview_at")
        if interview_at and interview_at <= timezone.now():
            self.add_error("interview_at", "Choose a time in the future.")
        if interview_at and not data.get("interview_details"):
            self.add_error("interview_details", "Tell the candidate where or how to attend.")
        return data
