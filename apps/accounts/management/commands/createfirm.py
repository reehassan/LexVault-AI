# apps/firms/management/commands/createfirm.py
from django.core.management.base import BaseCommand
from apps.firms.models import Firm

class Command(BaseCommand):
    help = "Create a new Firm."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Firm name")

    def handle(self, *args, **options):
        firm = Firm.objects.create(name=options["name"])
        self.stdout.write(
            self.style.SUCCESS(f"Created firm '{firm.name}' with id {firm.id}")
        )

# python manage.py createfirm --name "PixelLawFirm"