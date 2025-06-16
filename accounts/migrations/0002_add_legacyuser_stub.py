from django.db import migrations, models
import django.contrib.auth.models

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LegacyUser',
            fields=[
                # basta con el id; no se tocará la BD porque managed=False
                ('id', models.AutoField(primary_key=True, serialize=False)),
            ],
            options={
                'managed': False,   # <-- IMPORTANTE: ¡no altera tablas!
                'db_table': 'users',   # <-- la tabla real que ya existe
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
    ]
