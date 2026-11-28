from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .forms import FreelancerDocumentNumberField
from .models import FreelancerProfile, HirerAccessCode, Job, User


admin.site.site_header = "KaziLink Administration"
admin.site.site_title = "KaziLink Admin"
admin.site.index_title = "Manage KaziLink"


class SuperuserEditsOnly:
    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)


admin.site.unregister(Group)


@admin.register(Group)
class KaziLinkGroupAdmin(SuperuserEditsOnly, GroupAdmin):
    actions = ("add_all_freelancers", "add_all_hirers")

    @admin.action(permissions=["change"], description="Add all freelancers to selected group")
    def add_all_freelancers(self, request, queryset):
        self.add_role_members(request, queryset, User.Role.FREELANCER)

    @admin.action(permissions=["change"], description="Add all hirers to selected group")
    def add_all_hirers(self, request, queryset):
        self.add_role_members(request, queryset, User.Role.HIRER)

    def add_role_members(self, request, queryset, role):
        groups = list(queryset[:2])
        if len(groups) != 1:
            self.message_user(request, "Select exactly one destination group.", level=messages.ERROR)
            return

        group = groups[0]
        user_ids = list(User.objects.filter(role=role).values_list("pk", flat=True))
        group.user_set.add(*user_ids)
        self.message_user(
            request, f"{group.name} now includes all {len(user_ids)} accounts with the {role.label} role.",
            level=messages.SUCCESS,
        )


class FreelancerProfileInline(admin.StackedInline):
    model = FreelancerProfile
    fields = ("skills", "available", "document_type")
    readonly_fields = ("document_type",)
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class AccountChangeForm(UserChangeForm):
    new_freelancer_skills = forms.CharField(label="Skills", max_length=240, required=False)
    new_freelancer_available = forms.BooleanField(label="Available for work", required=False)
    new_freelancer_document_type = forms.ChoiceField(
        label="Document type",
        choices=[("", "Select document type"), *FreelancerProfile.DocumentType.choices],
        required=False,
    )
    new_freelancer_document_number = FreelancerDocumentNumberField(required=False)

    freelancer_fields = (
        "new_freelancer_skills", "new_freelancer_available",
        "new_freelancer_document_type", "new_freelancer_document_number",
    )
    freelancer_details = None

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("role") != User.Role.FREELANCER or hasattr(
            self.instance, "freelancer_profile"
        ):
            return cleaned_data

        for field in self.freelancer_fields:
            if field != "new_freelancer_available" and field in cleaned_data and not cleaned_data[field]:
                self.add_error(field, "This field is required when assigning the Freelancer role.")

        if all(field in cleaned_data for field in self.freelancer_fields):
            self.freelancer_details = {
                "skills": cleaned_data["new_freelancer_skills"],
                "available": cleaned_data["new_freelancer_available"],
                "document_type": cleaned_data["new_freelancer_document_type"],
                "document_hash": make_password(cleaned_data["new_freelancer_document_number"]),
            }
        return cleaned_data


@admin.register(User)
@method_decorator(sensitive_post_parameters("new_freelancer_document_number"), name="changeform_view")
class KaziLinkUserAdmin(SuperuserEditsOnly, UserAdmin):
    form = AccountChangeForm
    fieldsets = UserAdmin.fieldsets + (
        ("KaziLink profile", {
            "fields": ("role", "location"),
            "description": "Choose the role this account will use to sign in to KaziLink.",
        }),
    )
    list_display = ("username", "email", "role", "location", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active", "groups")
    search_fields = (*UserAdmin.search_fields, "location")
    inlines = (FreelancerProfileInline,)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj and self.has_change_permission(request, obj) and not hasattr(obj, "freelancer_profile"):
            return fieldsets + (("Freelancer setup", {
                "fields": self.form.freelancer_fields,
                "description": "Complete this section when assigning the Freelancer role.",
            }),)
        return fieldsets

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and form.freelancer_details is not None:
            FreelancerProfile.objects.create(user=obj, **form.freelancer_details)

    def get_inlines(self, request, obj=None):
        if obj and obj.role == User.Role.FREELANCER and hasattr(obj, "freelancer_profile"):
            return super().get_inlines(request, obj)
        return ()


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "hirer", "location", "pay", "duration", "posted_at")
    list_filter = ("posted_at",)
    search_fields = ("title", "hirer__username", "location")
    list_select_related = ("hirer",)
    readonly_fields = ("posted_at",)


@admin.register(HirerAccessCode)
class HirerAccessCodeAdmin(admin.ModelAdmin):
    change_list_template = "admin/marketplace/hireraccesscode/change_list.html"
    fields = ("id", "issued_at", "redeemed_at")
    readonly_fields = fields
    list_display = ("id", "issued_at", "redeemed_at")
    list_filter = ("issued_at", ("redeemed_at", admin.EmptyFieldListFilter))
    ordering = ("-issued_at",)

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    @method_decorator(require_http_methods(["GET", "POST"]))
    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied

        code = None
        if request.method == "POST":
            with transaction.atomic():
                record, code = HirerAccessCode.issue()
                self.log_addition(request, record, "Generated a hirer access code.")

        request.current_app = self.admin_site.name
        return TemplateResponse(request, "admin/marketplace/hireraccesscode/issue.html", {
            **self.admin_site.each_context(request),
            **(extra_context or {}),
            "title": "Hirer access code generated" if code else "Generate a hirer access code",
            "code": code,
        })

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
