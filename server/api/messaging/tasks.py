import logging
import json
from celery import shared_task
from .actions import generate_conversation_title
from .models import Conversation, Message, ConversationAlertRule, ConversationAlert, Tag
from .schemas import ConversationAnalysisResult
from api.authenticate.models import Organization, FeatureFlag, FeatureFlagAssignment, CredentialsManager
from api.authenticate.services import FeatureFlagService
from api.utils.openai_functions import create_structured_completion
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task
def async_generate_conversation_title(conversation_id: str):
    result = generate_conversation_title(conversation_id=conversation_id)
    return result


@shared_task
def widget_conversation_agent_task(
    *,
    conversation_id: str,
    user_inputs: list[dict],
    tool_names: list[str],
    agent_slug: str,
    widget_token: str,
    widget_session_id: str,
    regenerate_message_id: int | None = None,
):
    """
    Dedicated widget agent task entrypoint.
    Keeps widget-specific validation/routing separate from generic conversation_agent_task.
    """
    from api.ai_layers.tasks import conversation_agent_task

    try:
        conversation = Conversation.objects.select_related(
            "chat_widget", "widget_visitor_session"
        ).get(id=conversation_id)
    except Conversation.DoesNotExist:
        return {"status": "error", "error": "Conversation not found"}

    if not conversation.chat_widget or conversation.chat_widget.token != widget_token:
        return {"status": "error", "error": "Conversation does not belong to widget"}
    if (
        not conversation.widget_visitor_session
        or str(conversation.widget_visitor_session_id) != str(widget_session_id)
    ):
        return {"status": "error", "error": "Conversation does not belong to widget session"}

    # Widget route key is how streaming events are delivered to this visitor.
    route_key = f"widget_session:{widget_session_id}"
    return conversation_agent_task(
        conversation_id=conversation_id,
        user_inputs=user_inputs,
        tool_names=tool_names,
        agent_slugs=[agent_slug],
        multiagentic_modality="isolated",
        user_id=route_key,
        regenerate_message_id=regenerate_message_id,
    )


def get_organizations_with_feature_flag(feature_flag_name: str):
    """
    Obtiene todas las organizaciones que tienen un feature flag específico activado.
    
    Args:
        feature_flag_name: Nombre del feature flag a buscar
        
    Returns:
        QuerySet de organizaciones con el feature flag activado
    """
    try:
        feature_flag = FeatureFlag.objects.get(name=feature_flag_name)
        # Buscar asignaciones a nivel de organización (user__isnull=True) que estén habilitadas
        assignments = FeatureFlagAssignment.objects.filter(
            feature_flag=feature_flag,
            organization__isnull=False,
            user__isnull=True,
            enabled=True
        ).select_related('organization')
        
        # Extraer las organizaciones
        organizations = [assignment.organization for assignment in assignments]
        return organizations
    except FeatureFlag.DoesNotExist:
        logger.warning(f"Feature flag '{feature_flag_name}' does not exist")
        return []


@shared_task
def check_pending_conversations():
    """
    Busca todas las conversaciones pendientes de análisis de todas las organizaciones
    con el feature flag 'conversation-analysis' activado.
    Para cada conversación encontrada, orquesta la tarea analyze_single_conversation.
    """
    feature_flag_name = "conversation-analysis"
    
    # Obtener organizaciones con el feature flag activado
    organizations = get_organizations_with_feature_flag(feature_flag_name)
    
    if not organizations:
        logger.info(f"No organizations found with feature flag '{feature_flag_name}' enabled")
        return {"processed": 0, "organizations_checked": 0}
    
    logger.info(f"Found {len(organizations)} organizations with '{feature_flag_name}' enabled")
    
    # Obtener todos los usuarios de estas organizaciones
    from django.contrib.auth.models import User
    
    # Usuarios que son owners
    owner_users = Organization.objects.filter(
        id__in=[org.id for org in organizations]
    ).values_list('owner', flat=True)
    
    # Usuarios que son miembros (ahora a través de UserProfile.organization)
    member_users = User.objects.filter(
        profile__organization__in=organizations
    ).values_list('id', flat=True)
    
    # Combinar y obtener usuarios únicos
    all_users = set(list(owner_users) + list(member_users))
    
    if not all_users:
        logger.info("No users found in organizations with the feature flag enabled")
        return {"processed": 0, "organizations_checked": len(organizations)}
    
    # Atomically claim pending conversations to prevent duplicate processing
    with transaction.atomic():
        pending_conversations = list(
            Conversation.objects.select_for_update(skip_locked=True).filter(
                user__in=all_users,
                pending_analysis=True
            ).select_related('user')
        )
    conversation_count = len(pending_conversations)
    logger.info(f"Found {conversation_count} conversations pending analysis")
    
    # Orquestar tarea para cada conversación
    processed = 0
    for conversation in pending_conversations:
        try:
            analyze_single_conversation.delay(str(conversation.id))
            processed += 1
        except Exception as e:
            logger.error(f"Error scheduling analysis for conversation {conversation.id}: {str(e)}")
    
    logger.info(f"Successfully scheduled {processed} conversations for analysis")
    
    return {
        "processed": processed,
        "organizations_checked": len(organizations),
        "conversations_found": conversation_count
    }


def get_user_organization(user):
    """
    Obtiene la organización de un usuario (como owner o member).
    Retorna la primera organización encontrada.
    """
    if not user:
        return None
    
    # Buscar si el usuario es owner de alguna organización
    owned_org = Organization.objects.filter(owner=user).first()
    if owned_org:
        return owned_org
    
    # Buscar si el usuario tiene una organización en su perfil
    if hasattr(user, 'profile') and user.profile.organization:
        return user.profile.organization
    
    return None


@shared_task
def analyze_single_conversation(conversation_uuid: str):
    """
    Analiza una conversación individual para determinar si rompe alguna regla y levanta alertas.
    
    Args:
        conversation_uuid: UUID de la conversación a analizar
        
    La tarea:
    - Obtiene las alert rules activas de la organización
    - Verifica alertas previamente levantadas para evitar duplicados
    - Usa OpenAI para analizar si la conversación debe levantar alertas
    - Guarda las alertas levantadas en la base de datos
    - Marca la conversación como analizada
    """
    try:
        conversation = Conversation.objects.select_related('user').get(id=conversation_uuid)
        
        # Contar mensajes
        message_count = Message.objects.filter(conversation=conversation).count()
        
        if message_count == 0:
            logger.warning(f"Conversation {conversation_uuid} has no messages, skipping analysis")
            conversation.pending_analysis = False
            conversation.save()
            return {
                "conversation_uuid": conversation_uuid,
                "message_count": 0,
                "status": "skipped",
                "reason": "No messages"
            }
        
        logger.info(f"Analyzing conversation {conversation_uuid}: {message_count} messages to analyze")
        
        # Obtener la organización del usuario
        organization = get_user_organization(conversation.user)
        
        if not organization:
            logger.warning(f"User {conversation.user} has no organization, skipping analysis")
            conversation.pending_analysis = False
            conversation.save()
            return {
                "conversation_uuid": conversation_uuid,
                "status": "skipped",
                "reason": "No organization"
            }
        
        # Obtener credenciales de OpenAI
        api_key = None
        try:
            credentials = CredentialsManager.objects.get(organization=organization)
            api_key = credentials.openai_api_key
            if not api_key:
                logger.warning(f"Organization {organization.name} has no OpenAI API key, using default")
                api_key = None
        except CredentialsManager.DoesNotExist:
            logger.warning(f"Organization {organization.name} has no credentials manager, using default API key")
            api_key = None
        
        # Obtener tags habilitadas de la organización
        enabled_tags = Tag.objects.filter(
            organization=organization,
            enabled=True
        ).values('id', 'title')
        
        enabled_tags_list = list(enabled_tags)
        enabled_tags_json = json.dumps(enabled_tags_list, ensure_ascii=False, indent=2)
        logger.info(f"Found {len(enabled_tags_list)} enabled tags for organization {organization.name}")
        
        # Obtener alert rules activas y habilitadas de la organización
        alert_rules = ConversationAlertRule.objects.filter(
            organization=organization,
            enabled=True
        ).values('id', 'name', 'trigger', 'extractions')
        
        alert_rules_list = list(alert_rules)
        logger.info(f"Found {len(alert_rules_list)} active alert rules for organization {organization.name}")
        
        # Skip analysis if there are no alert rules and no tags configured
        if not alert_rules_list and not enabled_tags_list:
            logger.info(f"Organization {organization.name} has no alert rules or tags, skipping analysis for conversation {conversation_uuid}")
            conversation.pending_analysis = False
            conversation.save(update_fields=['pending_analysis'])
            return {
                "conversation_uuid": conversation_uuid,
                "message_count": message_count,
                "status": "skipped",
                "reason": "No alert rules or tags configured"
            }
        
        # Obtener alertas previamente levantadas para esta conversación (para evitar duplicados)
        existing_alerts = ConversationAlert.objects.filter(
            conversation=conversation
        ).values('alert_rule_id', 'status')
        
        existing_alert_rule_ids = {str(alert['alert_rule_id']) for alert in existing_alerts}
        logger.info(f"Found {len(existing_alert_rule_ids)} existing alerts for conversation {conversation_uuid}")
        
        # Obtener y formatear los mensajes de la conversación
        messages = Message.objects.filter(conversation=conversation).order_by('created_at')
        messages_context = "\n".join(
            [f"{message.type}: {message.text}" for message in messages]
        )
        
        # Formatear información de alert rules para el prompt
        alert_rules_info = []
        for rule in alert_rules_list:
            rule_info = {
                "id": str(rule['id']),
                "name": rule['name'],
                "trigger": rule['trigger'],
                "extractions": rule['extractions'] or {}
            }
            alert_rules_info.append(rule_info)
        
        # Formatear información de alertas existentes
        existing_alerts_info = []
        for alert in existing_alerts:
            existing_alerts_info.append({
                "alert_rule_id": str(alert['alert_rule_id']),
                "status": alert['status']
            })
        
        # Crear el prompt del sistema
        alert_rules_json = json.dumps(alert_rules_info, ensure_ascii=False, indent=2)
        existing_alerts_json = json.dumps(existing_alerts_info, ensure_ascii=False, indent=2)
        
        system_prompt = f"""Eres un analista experto de conversaciones. Tu tarea es analizar la conversación y:
1. Generar un resumen de la conversación en el mismo idioma en que se desarrolló
2. Determinar si debe levantarse alguna alerta según las reglas proporcionadas
3. Sugerir tags relevantes de la lista de tags habilitadas

REGLAS DE ALERTA DISPONIBLES:
{alert_rules_json}

TAGS HABILITADAS DISPONIBLES (puedes sugerir IDs de estas tags):
{enabled_tags_json}

ALERTAS YA LEVANTADAS (NO debes levantar alertas duplicadas para las mismas reglas):
{existing_alerts_json}

INSTRUCCIONES:
1. Analiza cuidadosamente la conversación
2. Genera un resumen conciso en el mismo idioma de la conversación
3. Sugiere tags relevantes (solo IDs de tags de la lista de tags habilitadas)
4. Evalúa si la conversación cumple con los requerimientos (trigger) de alguna de las reglas de alerta
5. NO levantes alertas para reglas que ya están en las alertas existentes (a menos que sea necesario por alguna razón especial)
6. Para cada alerta que levantes, proporciona:
   - El ID de la regla correspondiente
   - Los datos extraídos según lo especificado en el campo "extractions" de la regla
7. En el campo "reasoning", explica claramente por qué se levanta o no cada alerta

IMPORTANTE: Solo levanta alertas si la conversación realmente cumple con los requerimientos especificados en el campo "trigger" de cada regla."""
        
        # Realizar el análisis usando OpenAI con el schema de Pydantic
        try:
            analysis = create_structured_completion(
                model="gpt-4o",
                system_prompt=system_prompt,
                user_prompt=messages_context,
                response_format=ConversationAnalysisResult,
                api_key=api_key,
            )
            
            logger.info(f"Analysis completed for conversation {conversation_uuid}")
            logger.info(f"Reasoning: {(analysis.reasoning or '')[:200]}...")
            logger.info(f"Summary: {(analysis.summary or '')[:200]}...")
            logger.info(f"Suggested tags: {analysis.suggested_tags}")
            logger.info(f"Alerts to raise: {len(analysis.alerts)}")
            
            # Procesar y guardar las alertas levantadas
            alerts_raised = 0
            with transaction.atomic():
                # Guardar el resumen
                conversation.summary = analysis.summary
                
                # Asignar tags sugeridas (solo si existen y están habilitadas)
                if analysis.suggested_tags:
                    valid_tag_ids = list(Tag.objects.filter(
                        id__in=analysis.suggested_tags,
                        organization=organization,
                        enabled=True
                    ).values_list('id', flat=True))
                    
                    if valid_tag_ids:
                        conversation.tags = valid_tag_ids
                        logger.info(f"Assigned {len(valid_tag_ids)} tags to conversation {conversation_uuid}")
                    else:
                        logger.warning(f"No valid tags found from suggested tags: {analysis.suggested_tags}")
                
                for alert_data in analysis.alerts:
                    try:
                        # Verificar que la alert rule existe y está activa
                        alert_rule = ConversationAlertRule.objects.get(
                            id=alert_data.id,
                            organization=organization,
                            enabled=True
                        )
                        
                        # Verificar si ya existe una alerta para esta regla y conversación (evitar duplicados)
                        existing_alert = ConversationAlert.objects.filter(
                            conversation=conversation,
                            alert_rule=alert_rule
                        ).first()
                        
                        if existing_alert:
                            logger.info(f"Alert already exists for rule {alert_data.id} in conversation {conversation_uuid}, skipping")
                            continue
                        
                        # Crear la alerta
                        # Generar un título basado en el nombre de la regla y algún dato extraído
                        title = alert_rule.name
                        extractions = alert_data.extractions or {}
                        if extractions:
                            # Intentar crear un título más descriptivo con los datos extraídos
                            first_key = list(extractions.keys())[0] if extractions else None
                            if first_key:
                                title = f"{alert_rule.name} - {str(extractions.get(first_key, ''))[:30]}"
                        
                        ConversationAlert.objects.create(
                            title=title[:50],  # El campo tiene max_length=50
                            reasoning=analysis.reasoning,
                            extractions=extractions,
                            conversation=conversation,
                            alert_rule=alert_rule,
                            status="PENDING"
                        )
                        
                        alerts_raised += 1
                        logger.info(f"Alert raised for rule {alert_rule.name} (ID: {alert_data.id}) in conversation {conversation_uuid}")
                        
                    except ConversationAlertRule.DoesNotExist:
                        logger.warning(f"Alert rule {alert_data.id} not found or not enabled, skipping")
                        continue
                    except Exception as alert_error:
                        logger.error(f"Error creating alert for rule {alert_data.id}: {str(alert_error)}")
                        continue
                
                # Marcar la conversación como analizada
                conversation.pending_analysis = False
                conversation.save(update_fields=['summary', 'tags', 'pending_analysis'])
            
            logger.info(f"Conversation {conversation_uuid} analysis completed: {alerts_raised} alerts raised")
            
            return {
                "conversation_uuid": conversation_uuid,
                "message_count": message_count,
                "status": "completed",
                "alerts_raised": alerts_raised,
                "reasoning": analysis.reasoning
            }
            
        except Exception as openai_error:
            logger.error(f"OpenAI API error analyzing conversation {conversation_uuid}: {str(openai_error)}")
            # Marcar como procesado para evitar reintentos infinitos
            conversation.pending_analysis = False
            conversation.save()
            return {
                "conversation_uuid": conversation_uuid,
                "status": "error",
                "error": f"OpenAI API error: {str(openai_error)}"
            }
        
    except Conversation.DoesNotExist:
        logger.error(f"Conversation {conversation_uuid} not found")
        return {
            "conversation_uuid": conversation_uuid,
            "status": "error",
            "error": "Conversation not found"
        }
    except Exception as e:
        logger.error(f"Error analyzing conversation {conversation_uuid}: {str(e)}")
        # Intentar marcar como procesado para evitar reintentos infinitos
        try:
            conversation = Conversation.objects.get(id=conversation_uuid)
            conversation.pending_analysis = False
            conversation.save()
        except Exception as cleanup_error:
            logger.warning(f"Failed to mark conversation {conversation_uuid} as processed: {cleanup_error}")
        return {
            "conversation_uuid": conversation_uuid,
            "status": "error",
            "error": str(e)
        }
