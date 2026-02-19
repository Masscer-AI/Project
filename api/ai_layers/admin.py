from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django import forms
from django.db.models import Q
from .models import Agent, LanguageModel, AgentSession
from api.authenticate.services import FeatureFlagService
from api.authenticate.models import Organization
from api.messaging.models import ChatWidget
import json


class AgentAdminForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = "__all__"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = kwargs.pop('request', None)
        if request and request.user:
            user = request.user
            # Get user's organization
            user_org = None
            if hasattr(user, 'profile') and user.profile.organization:
                user_org = user.profile.organization
            
            # Check if user has the feature flag
            has_admin_flag, _ = FeatureFlagService.is_feature_enabled(
                "edit-organization-agent",
                organization=user_org,
                user=user
            )
            
            # If user has the flag, allow selecting organization
            # Otherwise, hide the organization field or set it to None
            if not has_admin_flag:
                # User without flag can only create agents for themselves
                self.fields['organization'].widget = forms.HiddenInput()
                self.fields['organization'].required = False
            else:
                # User with flag can select organization
                if user_org:
                    self.fields['organization'].queryset = Organization.objects.filter(
                        Q(id=user_org.id) | Q(owner=user)
                    )
                else:
                    self.fields['organization'].queryset = Organization.objects.filter(owner=user)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        request = getattr(self, 'request', None)
        if request and request.user:
            user = request.user
            has_admin_flag, _ = FeatureFlagService.is_feature_enabled(
                "edit-organization-agent",
                user=user
            )
            
            # If no organization is set and user doesn't have flag, set user
            if not instance.organization and not has_admin_flag:
                instance.user = user
            # If organization is set, user should be None (or could be set to creator)
            elif instance.organization:
                # Optionally set user to creator for tracking
                if not instance.user:
                    instance.user = user
        
        if commit:
            instance.save()
        return instance


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    form = AgentAdminForm
    list_display = ("name", "slug", "user", "organization", "is_public", "generate_widget_link")
    search_fields = ("name", "slug", "user__username", "organization__name")
    list_filter = ("is_public", "organization", "user")
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "slug", "user", "organization")
        }),
        ("Model Configuration", {
            "fields": ("model_provider", "model_slug", "llm", "temperature", "max_tokens", "top_p", 
                      "frequency_penalty", "presence_penalty")
        }),
        ("Agent Behavior", {
            "fields": ("system_prompt", "act_as", "salute", "conversation_title_prompt")
        }),
        ("Appearance", {
            "fields": ("profile_picture_url", "profile_picture_src", "openai_voice")
        }),
        ("Settings", {
            "fields": ("is_public", "default")
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.request = request
        return form
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        
        # Superusers can see all agents
        if user.is_superuser:
            return qs
        
        # Get user's organization
        user_org = None
        if hasattr(user, 'profile') and user.profile.organization:
            user_org = user.profile.organization
        
        # Non-superusers see their own agents + their organization's agents
        if user_org:
            return qs.filter(Q(user=user) | Q(organization=user_org))
        else:
            return qs.filter(user=user)
    
    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        
        user = request.user
        
        # Superusers can edit anything
        if user.is_superuser:
            return True
        
        user_org = None
        if hasattr(user, 'profile') and user.profile.organization:
            user_org = user.profile.organization
        
        has_admin_flag, _ = FeatureFlagService.is_feature_enabled(
            "edit-organization-agent",
            organization=user_org,
            user=user
        )
        
        # User can always edit their own agents
        if obj.user == user:
            return True
        
        # User with flag can edit organization agents
        if has_admin_flag and obj.organization == user_org:
            return True
        
        # User without flag cannot edit organization agents
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Same logic as has_change_permission
        return self.has_change_permission(request, obj)
    
    def generate_widget_link(self, obj):
        """Generate a link to create a chat widget for this agent"""
        if not obj.id:
            return "-"
        
        # Get request from admin instance
        request = getattr(self, '_request', None)
        if not request:
            return "-"
        
        user = request.user
        user_org = None
        if hasattr(user, 'profile') and user.profile.organization:
            user_org = user.profile.organization
        
        has_admin_flag, _ = FeatureFlagService.is_feature_enabled(
            "edit-organization-agent",
            organization=user_org,
            user=user
        )
        
        # Only show widget link if user can edit this agent
        can_edit = (obj.user == user) or (has_admin_flag and obj.organization == user_org)
        
        if not can_edit:
            return "-"
        
        # Check if widget already exists
        existing_widget = ChatWidget.objects.filter(agent=obj).first()
        if existing_widget:
            widget_url = reverse('admin:messaging_chatwidget_change', args=[existing_widget.id])
            return format_html(
                '<a href="{}">View Widget</a>',
                widget_url
            )
        
        # Create widget link
        create_url = reverse('admin:messaging_chatwidget_add')
        return format_html(
            '<a href="{}?agent={}">Create Widget</a>',
            create_url,
            obj.id
        )
    
    generate_widget_link.short_description = "Chat Widget"
    
    def changelist_view(self, request, extra_context=None):
        self._request = request
        return super().changelist_view(request, extra_context)
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        self._request = request
        return super().changeform_view(request, object_id, form_url, extra_context)


@admin.register(AgentSession)
class AgentSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task_type",
        "conversation",
        "agent_index",
        "iterations",
        "tool_calls_count",
        "started_at",
        "ended_at",
    )
    list_filter = ("task_type",)
    search_fields = ("conversation__id",)
    readonly_fields = (
        "id",
        "task_type",
        "conversation",
        "user_message",
        "assistant_message",
        "inputs_pretty",
        "outputs_pretty",
        "iterations",
        "tool_calls_count",
        "total_duration",
        "agent_index",
        "started_at",
        "ended_at",
        "dismissed_at",
    )

    fieldsets = (
        (
            "Execution",
            {
                "fields": (
                    "id",
                    "task_type",
                    "conversation",
                    "agent_index",
                    "iterations",
                    "tool_calls_count",
                    "total_duration",
                    "started_at",
                    "ended_at",
                    "dismissed_at",
                )
            },
        ),
        ("Message linkage", {"fields": ("user_message", "assistant_message")}),
        ("Inputs", {"fields": ("inputs_pretty",)}),
        ("Outputs", {"fields": ("outputs_pretty",)}),
    )

    def _pretty_json(self, data) -> str:
        try:
            return json.dumps(
                data if data is not None else {},
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        except Exception:
            return json.dumps({"error": "Failed to render JSON"}, indent=2)

    def _copy_button(self, textarea_id: str, label: str) -> str:
        # Uses execCommand for widest compatibility (Clipboard API can fail on non-HTTPS).
        return format_html(
            (
                "<button type=\"button\" class=\"button\" "
                "onclick=\"(function(){{"
                "var el=document.getElementById('{tid}');"
                "if(!el) return;"
                "el.focus(); el.select();"
                "try{{document.execCommand('copy');}}catch(e){{}}"
                "}})()\">{label}</button>"
            ),
            tid=textarea_id,
            label=label,
        )

    @admin.display(description="Inputs")
    def inputs_pretty(self, obj: AgentSession):
        inputs = obj.inputs or {}
        agent = inputs.get("agent") or {}
        model = inputs.get("model") or {}
        tool_names = inputs.get("tool_names") or []
        user_inputs = inputs.get("user_inputs") or []
        prev_messages = inputs.get("prev_messages") or []

        textarea_id = f"agentsession_inputs_{obj.pk}"
        pretty = self._pretty_json(inputs)

        summary_html = format_html(
            """
            <table style="width: 100%; max-width: 1000px;">
              <tbody>
                <tr><th style="text-align:left; width: 220px;">Agent</th><td>{agent_name} ({agent_slug})</td></tr>
                <tr><th style="text-align:left;">Model</th><td>{model_slug} ({provider})</td></tr>
                <tr><th style="text-align:left;">Tool names</th><td>{tools}</td></tr>
                <tr><th style="text-align:left;">User inputs</th><td>{user_inputs_count}</td></tr>
                <tr><th style="text-align:left;">Prev messages</th><td>{prev_messages_count}</td></tr>
                <tr><th style="text-align:left;">Max iterations</th><td>{max_iterations}</td></tr>
                <tr><th style="text-align:left;">Modality</th><td>{modality}</td></tr>
              </tbody>
            </table>
            """,
            agent_name=agent.get("name") or "-",
            agent_slug=agent.get("slug") or "-",
            model_slug=model.get("slug") or "-",
            provider=model.get("provider") or "-",
            tools=", ".join(tool_names) if tool_names else "-",
            user_inputs_count=len(user_inputs),
            prev_messages_count=len(prev_messages),
            max_iterations=inputs.get("max_iterations", "-"),
            modality=inputs.get("multiagentic_modality", "-"),
        )

        return format_html(
            """
            <div style="display:flex; align-items:center; gap:8px; margin: 8px 0;">
              {copy_btn}
              <span style="opacity:0.7;">{chars} chars</span>
            </div>
            <details open style="margin: 6px 0 10px 0;">
              <summary style="cursor:pointer;">Summary</summary>
              <div style="margin-top: 8px;">{summary}</div>
            </details>
            <details style="margin: 6px 0 0 0;">
              <summary style="cursor:pointer;">Raw JSON</summary>
              <div style="margin-top: 8px;">
                <textarea id="{tid}" readonly
                  style="width: 100%; min-height: 320px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;"
                >{json_text}</textarea>
              </div>
            </details>
            """,
            copy_btn=self._copy_button(textarea_id, "Copy inputs JSON"),
            chars=len(pretty),
            summary=summary_html,
            tid=textarea_id,
            json_text=pretty,
        )

    @admin.display(description="Outputs")
    def outputs_pretty(self, obj: AgentSession):
        outputs = obj.outputs or {}
        output_val = outputs.get("output") or {}
        status = outputs.get("status") or "-"
        error = outputs.get("error") or None
        usage = outputs.get("usage") or {}

        textarea_id = f"agentsession_outputs_{obj.pk}"
        pretty = self._pretty_json(outputs)

        # Best-effort preview for convenience
        preview = None
        if isinstance(output_val, dict):
            if output_val.get("type") == "string":
                preview = output_val.get("value")
            elif output_val.get("type") == "json":
                preview = self._pretty_json(output_val.get("value"))
        if isinstance(preview, str) and len(preview) > 800:
            preview = preview[:800] + "\n…"

        summary_html = format_html(
            """
            <table style="width: 100%; max-width: 1000px;">
              <tbody>
                <tr><th style="text-align:left; width: 220px;">Status</th><td>{status}</td></tr>
                <tr><th style="text-align:left;">Prompt tokens</th><td>{pt}</td></tr>
                <tr><th style="text-align:left;">Completion tokens</th><td>{ct}</td></tr>
                <tr><th style="text-align:left;">Total tokens</th><td>{tt}</td></tr>
                <tr><th style="text-align:left;">Has error</th><td>{has_error}</td></tr>
              </tbody>
            </table>
            """,
            status=status,
            pt=usage.get("prompt_tokens", 0),
            ct=usage.get("completion_tokens", 0),
            tt=usage.get("total_tokens", 0),
            has_error="yes" if error else "no",
        )

        error_block = ""
        if error:
            error_pretty = self._pretty_json(error)
            error_block = format_html(
                """
                <details open style="margin: 10px 0;">
                  <summary style="cursor:pointer;">Error</summary>
                  <pre style="margin-top:8px; white-space: pre-wrap;">{e}</pre>
                </details>
                """,
                e=error_pretty,
            )

        preview_block = ""
        if preview:
            preview_block = format_html(
                """
                <details open style="margin: 10px 0;">
                  <summary style="cursor:pointer;">Output preview</summary>
                  <pre style="margin-top:8px; white-space: pre-wrap;">{p}</pre>
                </details>
                """,
                p=preview,
            )

        return format_html(
            """
            <div style="display:flex; align-items:center; gap:8px; margin: 8px 0;">
              {copy_btn}
              <span style="opacity:0.7;">{chars} chars</span>
            </div>
            <details open style="margin: 6px 0 10px 0;">
              <summary style="cursor:pointer;">Summary</summary>
              <div style="margin-top: 8px;">{summary}</div>
              {preview}
              {error_block}
            </details>
            <details style="margin: 6px 0 0 0;">
              <summary style="cursor:pointer;">Raw JSON</summary>
              <div style="margin-top: 8px;">
                <textarea id="{tid}" readonly
                  style="width: 100%; min-height: 320px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;"
                >{json_text}</textarea>
              </div>
            </details>
            """,
            copy_btn=self._copy_button(textarea_id, "Copy outputs JSON"),
            chars=len(pretty),
            summary=summary_html,
            preview=preview_block,
            error_block=mark_safe(error_block) if error_block else "",
            tid=textarea_id,
            json_text=pretty,
        )


@admin.register(LanguageModel)
class LanguageModelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "pricing_table",
        "provider",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "slug", "provider__name")
    list_filter = ("provider",)

    # pricing table
    def pricing_table(self, obj):
        # Show a table with the pricing
        return mark_safe(
            f"""<table >
            <tr>
                <th>Prompt</th>
                <th>Output</th>
            </tr>
            <tr>
                <td>{obj.pricing['text']['prompt']}</td>
                <td>{obj.pricing['text']['output']}</td>
            </tr>
            </table>"""
        )
