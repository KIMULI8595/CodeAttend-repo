from django.db import migrations


def activate_staff_accounts(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_staff=True).update(account_status="ACTIVE", is_active=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_alter_user_phone_number")]
    operations = [migrations.RunPython(activate_staff_accounts, migrations.RunPython.noop)]
