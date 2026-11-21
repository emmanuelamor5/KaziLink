import hashlib
import secrets

from django.core.management.base import BaseCommand

from marketplace.models import HirerAccessCode


class Command(BaseCommand):
    help = "Issue a one-time KaziLink hirer requirement ID."

    def handle(self, *args, **options):
        code = secrets.token_hex(16).upper()
        HirerAccessCode.objects.create(digest=hashlib.sha256(code.encode()).hexdigest())
        self.stdout.write(code)
