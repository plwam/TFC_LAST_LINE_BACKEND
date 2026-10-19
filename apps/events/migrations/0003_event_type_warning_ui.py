# Ajout des types WARNING_ISSUED et UI_TAMPERING (retour candidat, 02b_SDK_RETOUR_CANDIDAT.md §4).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0002_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="type",
            field=models.CharField(
                choices=[
                    ("FOCUS_LOST", "FOCUS_LOST"),
                    ("TAB_SWITCH", "TAB_SWITCH"),
                    ("COPY_PASTE_TEXT", "COPY_PASTE_TEXT"),
                    ("CLIPBOARD_IMAGE_PASTE", "CLIPBOARD_IMAGE_PASTE"),
                    ("PAGE_EXIT", "PAGE_EXIT"),
                    ("DOM_TAMPERING", "DOM_TAMPERING"),
                    ("DEVTOOLS_OPEN", "DEVTOOLS_OPEN"),
                    ("FULLSCREEN_EXIT", "FULLSCREEN_EXIT"),
                    ("PRINT_ATTEMPT", "PRINT_ATTEMPT"),
                    ("SUSPICIOUS_KEY_COMBO", "SUSPICIOUS_KEY_COMBO"),
                    ("IDLE_TIMEOUT", "IDLE_TIMEOUT"),
                    ("MULTI_MONITOR_DETECTED", "MULTI_MONITOR_DETECTED"),
                    ("AUTOMATION_DETECTED", "AUTOMATION_DETECTED"),
                    ("EXTENSION_HEARTBEAT_LOST", "EXTENSION_HEARTBEAT_LOST"),
                    ("SIMULATED_EVENT_DETECTED", "SIMULATED_EVENT_DETECTED"),
                    ("NO_FACE_DETECTED", "NO_FACE_DETECTED"),
                    ("MULTIPLE_FACES", "MULTIPLE_FACES"),
                    ("FORBIDDEN_OBJECT_DETECTED", "FORBIDDEN_OBJECT_DETECTED"),
                    ("VIRTUAL_DEVICE_DETECTED", "VIRTUAL_DEVICE_DETECTED"),
                    ("GAZE_AWAY_SUSTAINED", "GAZE_AWAY_SUSTAINED"),
                    ("REPEATED_HEAD_TURN", "REPEATED_HEAD_TURN"),
                    ("HANDS_VISIBLE_SUSTAINED", "HANDS_VISIBLE_SUSTAINED"),
                    ("AUDIO_KEYWORD_MATCH", "AUDIO_KEYWORD_MATCH"),
                    ("MULTIPLE_VOICES", "MULTIPLE_VOICES"),
                    ("TAB_CHANGE_EXT", "TAB_CHANGE_EXT"),
                    ("NAVIGATION_EXT", "NAVIGATION_EXT"),
                    ("SUSPICIOUS_ENVIRONMENT", "SUSPICIOUS_ENVIRONMENT"),
                    ("WARNING_ISSUED", "WARNING_ISSUED"),
                    ("UI_TAMPERING", "UI_TAMPERING"),
                ],
                db_index=True,
                max_length=40,
            ),
        ),
    ]
