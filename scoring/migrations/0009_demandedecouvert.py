from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('scoring', '0008_demandecredit_ia_decision_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DemandeDecouvert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('montant_souhaite', models.DecimalField(decimal_places=2, max_digits=10)),
                ('statut', models.CharField(choices=[('EN_ATTENTE', 'En attente'), ('ACCEPTEE', 'Acceptée'), ('REFUSEE', 'Refusée')], default='EN_ATTENTE', max_length=15)),
                ('expire_le', models.DateField(blank=True, null=True)),
                ('commentaire_admin', models.TextField(blank=True)),
                ('cree_le', models.DateTimeField(auto_now_add=True)),
                ('mis_a_jour_le', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='demandes_decouvert', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-cree_le'],
            },
        ),
    ]
