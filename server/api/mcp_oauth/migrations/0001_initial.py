from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("ai_layers", "0029_mcpclient_allowed_tool_names"),
        ("authenticate", "0025_organizationtenant"),
        migrations.swappable_dependency("auth.User"),
    ]

    operations = [
        migrations.CreateModel(
            name="OAuthClient",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("client_id", models.CharField(db_index=True, max_length=512, unique=True)),
                ("client_secret_hash", models.CharField(blank=True, default="", max_length=64)),
                ("client_name", models.CharField(max_length=255)),
                ("redirect_uris", models.JSONField(blank=True, default=list)),
                ("token_endpoint_auth_method", models.CharField(default="none", max_length=32)),
                ("grant_types", models.JSONField(blank=True, default=list)),
                ("scope", models.CharField(blank=True, default="mcp offline_access", max_length=255)),
                (
                    "registration_source",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("dcr", "Dynamic Client Registration"),
                            ("cimd", "Client ID Metadata Document"),
                        ],
                        default="manual",
                        max_length=16,
                    ),
                ),
                ("cimd_url", models.URLField(blank=True, default="", max_length=512)),
                ("disabled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="oauth_clients",
                        to="authenticate.organization",
                    ),
                ),
                (
                    "owner_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_clients",
                        to="auth.user",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="OAuthAuthorizationRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("redirect_uri", models.TextField()),
                ("state", models.CharField(blank=True, default="", max_length=512)),
                ("code_challenge", models.CharField(max_length=128)),
                ("code_challenge_method", models.CharField(default="S256", max_length=16)),
                ("scope", models.CharField(blank=True, default="", max_length=255)),
                ("resource", models.TextField()),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="authorization_requests",
                        to="mcp_oauth.oauthclient",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_authorization_requests",
                        to="auth.user",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="OAuthAuthorizationCode",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("code_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("redirect_uri", models.TextField()),
                ("code_challenge", models.CharField(max_length=128)),
                ("scope", models.CharField(blank=True, default="", max_length=255)),
                ("resource", models.TextField()),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="authorization_codes",
                        to="mcp_oauth.oauthclient",
                    ),
                ),
                (
                    "mcp_client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_authorization_codes",
                        to="ai_layers.mcpclient",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_authorization_codes",
                        to="auth.user",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OAuthAccessToken",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("scope", models.CharField(blank=True, default="", max_length=255)),
                ("resource", models.TextField()),
                ("expires_at", models.DateTimeField()),
                ("revoked", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="access_tokens",
                        to="mcp_oauth.oauthclient",
                    ),
                ),
                (
                    "mcp_client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_access_tokens",
                        to="ai_layers.mcpclient",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_access_tokens",
                        to="auth.user",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OAuthRefreshToken",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("family_id", models.UUIDField(db_index=True)),
                ("scope", models.CharField(blank=True, default="", max_length=255)),
                ("resource", models.TextField()),
                ("expires_at", models.DateTimeField()),
                ("rotated_at", models.DateTimeField(blank=True, null=True)),
                ("revoked", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="refresh_tokens",
                        to="mcp_oauth.oauthclient",
                    ),
                ),
                (
                    "mcp_client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_refresh_tokens",
                        to="ai_layers.mcpclient",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_refresh_tokens",
                        to="auth.user",
                    ),
                ),
            ],
        ),
    ]
