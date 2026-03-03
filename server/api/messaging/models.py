import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from api.authenticate.models import PublishableToken, Organization


def _message_attachment_expires_default():
    return timezone.now() + timezone.timedelta(days=30)


class Conversation(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("archived", "Archived"),
        ("deleted", "Deleted"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="conversations",
        help_text="Organization that owns this conversation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    public_token = models.ForeignKey(
        PublishableToken, on_delete=models.SET_NULL, null=True, blank=True
    )
    chat_widget = models.ForeignKey(
        "ChatWidget",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    widget_visitor_session = models.ForeignKey(
        "WidgetVisitorSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    tags = models.JSONField(
        default=list, 
        blank=True,
        help_text="Lista de IDs de tags asociadas a esta conversación (solo tags habilitadas)"
    )
    background_image_src = models.TextField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True, help_text="Resumen de la conversación generado por la IA")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    last_message_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    pending_analysis = models.BooleanField(
        default=False,
        help_text="Indica si la conversación tiene un análisis pendiente de procesar"
    )

    def __str__(self):
        if self.title:
            return self.title

        return f"Conversation({self.id})"

    def cut_from(self, message_id):
        # This must delete all messages after the given message id
        Message.objects.filter(conversation=self, id__gt=message_id).delete()

    def generate_title(self):
        if not self.title:
            from .tasks import async_generate_conversation_title

            async_generate_conversation_title.delay(self.id)

    def get_all_messages_context(self):
        return "\n".join(
            [f"{message.type}: {message.text}\n" for message in self.messages.all()]
        )


class MessageAttachment(models.Model):
    """
    Temporary storage for files attached to messages (images, audio, etc.).
    Files expire after 30 days and can be cleaned up by a periodic task.

    Primary relation is to Message. Conversation is also stored for cases where
    the attachment is uploaded before the message exists (e.g. agent task flow).
    User and agent are optional (e.g. user-uploaded vs agent-generated).
    """

    KIND_CHOICES = [
        ("file", "File"),
        ("rag_document", "RAG Document"),
        ("website", "Website"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        "Message",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachment_files",
        help_text="The message this attachment belongs to (set when message is created)",
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="message_attachments",
        help_text="Conversation context; required when uploading before message exists",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="message_attachments",
    )
    agent = models.ForeignKey(
        "ai_layers.Agent",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="message_attachments",
    )
    kind = models.CharField(
        max_length=20,
        choices=KIND_CHOICES,
        default="file",
        help_text="Attachment kind: file upload, RAG document reference, or website reference",
    )
    file = models.FileField(upload_to="message_attachments/%Y/%m/", null=True, blank=True)
    rag_document = models.ForeignKey(
        "rag.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="message_attachments",
    )
    url = models.URLField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    content_type = models.CharField(max_length=100, blank=True, default="")
    expires_at = models.DateTimeField(
        default=_message_attachment_expires_default,
        help_text="After this date the attachment can be deleted (default: 30 days)",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"MessageAttachment({self.id}, kind={self.kind})"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.kind == "file":
            if not self.file:
                raise ValidationError({"file": "file is required when kind='file'."})
            if self.rag_document_id:
                raise ValidationError(
                    {"rag_document": "rag_document must be empty when kind='file'."}
                )
            if self.url:
                raise ValidationError({"url": "url must be empty when kind='file'."})
            if self.expires_at is None:
                self.expires_at = _message_attachment_expires_default()
        elif self.kind == "rag_document":
            if not self.rag_document_id:
                raise ValidationError(
                    {"rag_document": "rag_document is required when kind='rag_document'."}
                )
            if self.file:
                raise ValidationError({"file": "file must be empty when kind='rag_document'."})
            if self.url:
                raise ValidationError({"url": "url must be empty when kind='rag_document'."})
            self.expires_at = None
            self.content_type = self.content_type or "application/rag_document"
        elif self.kind == "website":
            if not self.url:
                raise ValidationError({"url": "url is required when kind='website'."})
            if self.file:
                raise ValidationError({"file": "file must be empty when kind='website'."})
            if self.rag_document_id:
                raise ValidationError(
                    {"rag_document": "rag_document must be empty when kind='website'."}
                )
            self.expires_at = None
            self.content_type = self.content_type or "text/html"
        else:
            raise ValidationError({"kind": f"Unknown kind '{self.kind}'."})


class Message(models.Model):
    TYPE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    text = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    versions = models.JSONField(default=list, blank=True)
    rag_sources = models.JSONField(default=list, blank=True)
    browse_sources = models.JSONField(default=list, blank=True)
    agents = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.type}: {self.text[:50]}"

    def save(self, *args, **kwargs):
        is_create = self.pk is None
        super().save(*args, **kwargs)
        if is_create and self.conversation_id:
            conv = self.conversation
            conv.last_message_at = self.created_at
            if conv.status in ("active", "inactive"):
                conv.status = "active"
            conv.save(update_fields=["last_message_at", "status", "updated_at"])


class SharedConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    valid_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SharedConversation({self.id})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class ChatWidget(models.Model):
    token = models.CharField(max_length=64, unique=True, db_index=True, blank=True)
    name = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    style = models.JSONField(default=dict, blank=True)
    web_search_enabled = models.BooleanField(default=False)
    rag_enabled = models.BooleanField(default=False)
    plugins_enabled = models.JSONField(default=list, blank=True)
    agent = models.ForeignKey(
        "ai_layers.Agent", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self):
        return f"ChatWidget({self.name})"


class WidgetVisitorSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    widget = models.ForeignKey(
        ChatWidget, on_delete=models.CASCADE, related_name="visitor_sessions"
    )
    visitor_id = models.CharField(max_length=64, db_index=True)
    origin = models.CharField(max_length=255, blank=True, default="")
    user_agent = models.TextField(blank=True, default="")
    expires_at = models.DateTimeField()
    last_seen_at = models.DateTimeField(auto_now=True)
    is_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("widget", "visitor_id"),)

    def __str__(self):
        return f"WidgetVisitorSession(widget={self.widget_id}, visitor={self.visitor_id})"


class ConversationAlertRule(models.Model):
    """
    Define los parámetros que deben cumplirse para levantar una alerta,
    a qué conversaciones o agentes aplica esta regla, y si está activada o no.
    """

    SCOPE_CHOICES = [
        ("all_conversations", "All Conversations"),
        ("selected_agents", "Selected Agents"),
    ]

    NOTIFY_TO_CHOICES = [
        ("all_staff", "All Staff"),
        ("selected_members", "Selected Members"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, help_text="Nombre de la regla de alerta")
    trigger = models.TextField(
        help_text="Explicación de los parámetros que deben cumplirse para levantar esta alerta"
    )
    extractions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Los datos que la IA debe extraer de la conversación (ej: Nombre, fecha, problema, etc)",
    )
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default="all_conversations",
        help_text="A qué conversaciones o agentes aplica esta regla",
    )
    enabled = models.BooleanField(
        default=True, help_text="Si esta regla está activada o no"
    )
    notify_to = models.CharField(
        max_length=20,
        choices=NOTIFY_TO_CHOICES,
        default="all_staff",
        help_text="A quién notificar cuando se active esta alerta",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="alert_rules",
        help_text="Organización a la que pertenece esta regla",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_alert_rules",
        help_text="Usuario que creó esta regla",
    )
    agents = models.ManyToManyField(
        "ai_layers.Agent",
        blank=True,
        related_name="alert_rules",
        help_text="Agentes seleccionados (solo aplica si scope='selected_agents')",
    )
    selected_members = models.ManyToManyField(
        User,
        blank=True,
        related_name="subscribed_alert_rules",
        help_text="Miembros seleccionados para notificar (solo aplica si notify_to='selected_members')",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conversation Alert Rule"
        verbose_name_plural = "Conversation Alert Rules"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class ConversationAlert(models.Model):
    """
    Define las alertas que han sido detectadas por el sistema.
    Está relacionado a una conversación y a una regla.
    """

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("NOTIFIED", "Notified"),
        ("RESOLVED", "Resolved"),
        ("DISMISSED", "Dismissed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(
        max_length=50, help_text="Título de la alerta (creado por la IA)"
    )
    reasoning = models.TextField(
        help_text="Explicación de la IA de por qué se levantó esta alerta"
    )
    extractions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extracción de datos de la IA: JSON que contiene los datos extraídos de la conversación",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="PENDING",
        help_text="Estado de la alerta",
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="alerts",
        help_text="Conversación que generó esta alerta",
    )
    alert_rule = models.ForeignKey(
        ConversationAlertRule,
        on_delete=models.CASCADE,
        related_name="alerts",
        help_text="Regla que generó esta alerta",
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_alerts",
        help_text="Usuario que resolvió esta alerta",
    )
    dismissed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dismissed_alerts",
        help_text="Usuario que desechó esta alerta",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conversation Alert"
        verbose_name_plural = "Conversation Alerts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.alert_rule.name} ({self.status})"


class AlertSubscription(models.Model):
    """
    Suscripciones de usuarios a reglas de alerta.
    Los usuarios suscritos serán los primeros en enterarse de una alerta.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="alert_subscriptions",
        help_text="Usuario suscrito a esta alerta",
    )
    alert_rule = models.ForeignKey(
        ConversationAlertRule,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        help_text="Regla de alerta a la que el usuario se está suscribiendo",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Alert Subscription"
        verbose_name_plural = "Alert Subscriptions"
        unique_together = [["user", "alert_rule"]]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} subscribed to {self.alert_rule.name}"


class Tag(models.Model):
    """
    Modelo para etiquetas de conversaciones.
    Cada organización puede tener sus propias tags habilitadas.
    """
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=50, help_text="Título de la etiqueta (máximo 50 caracteres)")
    description = models.TextField(blank=True, help_text="Descripción detallada de la etiqueta")
    color = models.CharField(max_length=7, default="#4a9eff", help_text="Color de la etiqueta en formato hexadecimal")
    enabled = models.BooleanField(default=True, help_text="Indica si la etiqueta está habilitada")
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="tags",
        help_text="Organización a la que pertenece esta etiqueta"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ["title"]
        unique_together = [["title", "organization"]]  # Evitar tags duplicadas en la misma org

    def __str__(self):
        return f"{self.title} ({self.organization.name})"