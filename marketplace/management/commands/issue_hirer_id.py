from django.core.management.base import BaseCommand

from marketplace.models import HirerAccessCode


class Command(BaseCommand):
    help = "Issue a one-time KaziLink hirer requirement ID."

    def handle(self, *args, **options):
        _, code = HirerAccessCode.issue()
        self.stdout.write(code)
