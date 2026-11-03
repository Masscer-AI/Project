from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_layers', '0038_agent_reasoning_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='agent',
            name='icon',
            field=models.CharField(choices=[('robot', 'Robot'), ('sparkles', 'Sparkles'), ('user', 'Person'), ('users', 'People'), ('message', 'Message'), ('headset', 'Headset'), ('briefcase', 'Briefcase'), ('building', 'Building'), ('building-bank', 'Bank'), ('scale', 'Scale'), ('gavel', 'Gavel'), ('shield', 'Shield'), ('shield-check', 'Verified shield'), ('lock', 'Lock'), ('book', 'Book'), ('books', 'Books'), ('school', 'School'), ('file-text', 'Document'), ('search', 'Search'), ('bulb', 'Idea'), ('chart-bar', 'Chart'), ('calculator', 'Calculator'), ('database', 'Database'), ('code', 'Code'), ('stethoscope', 'Health'), ('leaf', 'Leaf'), ('world', 'World'), ('mail', 'Mail'), ('phone', 'Phone'), ('star', 'Star')], default='robot', max_length=40),
        ),
    ]
