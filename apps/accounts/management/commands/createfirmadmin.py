from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from apps.firms.models import Firm


User = get_user_model()


class Command(BaseCommand):
    help = "Create an admin user for a specific firm."

    def add_arguments(self, parser):
        parser.add_argument(
            "--firm",
            required=True,
            help="Firm ID (UUID)",
        )

        parser.add_argument(
            "--username",
            required=True,
            help="Username",
        )

        parser.add_argument(
            "--email",
            required=True,
            help="Email address",
        )

        parser.add_argument(
            "--password",
            required=True,
            help="Password",
        )

    def handle(self, *args, **options):
        try:
            firm = Firm.objects.get(pk=options["firm"])
        except Firm.DoesNotExist:
            raise CommandError("Firm not found.")

        if User.objects.filter(
            firm=firm,
            username=options["username"],
        ).exists():
            raise CommandError(
                "A user with this username already exists in this firm."
            )

        user = User.objects.create_superuser(
            username=options["username"],
            email=options["email"],
            password=options["password"],
            firm=firm,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created admin '{user.username}' for '{firm.name}'."
            )
        )


# python manage.py createfirm --name "PixelLawFirm"
# python manage.py createfirmadmin --firm <uuid> --username areebahassan --email areeba@pixellawfirm.com --password ...

# python manage.py shell -c "
# from django.contrib.auth import get_user_model
# User = get_user_model()
# u = User.objects.get(username='areebahassan')
# print(u.id, u.username, u.email, u.firm.name, u.is_superuser, u.is_staff)
# "

# python manage.py shell -c "
# from django.contrib.auth import get_user_model
# User = get_user_model()
# u = User.objects.get(username='areebahassan')
# print(u.check_password('qazqaz786'))
# "

# firm 'SamarJafriLaws' 
# id 019f41bd-4219-73c9-8680-6d46e5b5d9f8
# username samarjafri
# email samarjafri@law.com
# password samarjaffri123
# admin 'samarjafri' for 'SamarJafriLaws'.


