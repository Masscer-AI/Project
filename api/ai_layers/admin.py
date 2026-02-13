from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django import forms
from django.db.models import Q
from .models import Agent, LanguageModel
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
