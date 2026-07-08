from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SearchHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target', models.CharField(default='video', max_length=16)),
                ('query', models.CharField(max_length=255)),
                ('max_results', models.PositiveSmallIntegerField(default=50)),
                ('order', models.CharField(default='viewCount', max_length=32)),
                ('lower_threshold', models.PositiveIntegerField(default=100000)),
                ('upper_threshold', models.PositiveIntegerField(default=500000)),
                ('min_duration', models.PositiveIntegerField(default=0)),
                ('max_duration', models.PositiveIntegerField(default=60)),
                ('date_option', models.CharField(default='none', max_length=16)),
                ('results_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
