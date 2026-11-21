from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        FREELANCER = "freelancer", "Freelancer"
        HIRER = "hirer", "Hirer"

    role = models.CharField(max_length=10, choices=Role.choices, blank=True)
    location = models.CharField(max_length=100, blank=True)


class FreelancerProfile(models.Model):
    class DocumentType(models.TextChoices):
        NATIONAL_ID = "national_id", "National ID"
        PASSPORT = "passport", "Passport"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="freelancer_profile", limit_choices_to={"role": User.Role.FREELANCER},
    )
    skills = models.CharField(max_length=240)
    available = models.BooleanField(default=True)
    document_type = models.CharField(max_length=12, choices=DocumentType.choices)
    document_hash = models.CharField(max_length=128, editable=False)


class HirerAccessCode(models.Model):
    digest = models.CharField(max_length=64, unique=True, editable=False)
    issued_at = models.DateTimeField(auto_now_add=True)
    redeemed_at = models.DateTimeField(null=True, blank=True, editable=False)


class Job(models.Model):
    hirer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="jobs", limit_choices_to={"role": User.Role.HIRER},
    )
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=2000)
    location = models.CharField(max_length=100)
    duration = models.CharField(max_length=100)
    pay = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    expectations = models.TextField(max_length=1000)
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-posted_at", "-pk"]

    def __str__(self):
        return self.title
