from django.db import migrations


def require_existing_users_password_change(apps, schema_editor):
    User = apps.get_model("portal", "User")
    User.objects.filter(is_active=True, is_superuser=False).update(must_change_password=True)


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0003_user_must_change_password"),
    ]

    operations = [
        migrations.RunPython(require_existing_users_password_change, migrations.RunPython.noop),
    ]
