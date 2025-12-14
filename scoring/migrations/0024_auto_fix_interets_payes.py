from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('scoring', '0023_demandecredit_capital_initial_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandecredit',
            name='interets_payes',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
