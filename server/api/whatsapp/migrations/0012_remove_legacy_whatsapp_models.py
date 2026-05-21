# Remove WSConversation / WSMessage / WSContact (unified on messaging.Conversation)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("whatsapp", "0011_wsnumber_capabilities"),
    ]

    operations = [
        migrations.DeleteModel(name="WSMessage"),
        migrations.DeleteModel(name="WSConversation"),
        migrations.DeleteModel(name="WSContact"),
    ]
