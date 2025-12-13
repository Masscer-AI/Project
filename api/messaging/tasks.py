import logging
import json
from celery import shared_task
from .actions import generate_conversation_title
from .models import Conversation, Message
from .schemas import ConversationAnalysis
from api.authenticate.models import Organization, FeatureFlag, FeatureFlagAssignment, CredentialsManager
from api.authenticate.services import FeatureFlagService
from api.utils.openai_functions import create_structured_completion
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task
def async_generate_conversation_title(conversation_id: str):
    result = generate_conversation_title(conversation_id=conversation_id)
    return result


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
        
        # Obtener alert rules activas y habilitadas de la organización
        alert_rules = ConversationAlertRule.objects.filter(
            organization=organization,
            enabled=True
        ).values('id', 'name', 'trigger', 'extractions')
        
        if not alert_rules.exists():
            logger.info(f"No active alert rules found for organization {organization.name}, marking conversation as analyzed")
            conversation.pending_analysis = False
            conversation.save()
            return {
                "conversation_uuid": conversation_uuid,
                "status": "completed",
                "alerts_raised": 0,
                "reason": "No alert rules configured"
            }
        
        alert_rules_list = list(alert_rules)
        logger.info(f"Found {len(alert_rules_list)} active alert rules for organization {organization.name}")
        
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
        
        system_prompt = f"""Eres un analista experto de conversaciones. Tu tarea es analizar la conversación y determinar si debe levantarse alguna alerta según las reglas proporcionadas.

REGLAS DE ALERTA DISPONIBLES:
{alert_rules_json}

ALERTAS YA LEVANTADAS (NO debes levantar alertas duplicadas para las mismas reglas):
{existing_alerts_json}

INSTRUCCIONES:
1. Analiza cuidadosamente la conversación
2. Evalúa si la conversación cumple con los requerimientos (trigger) de alguna de las reglas de alerta
3. NO levantes alertas para reglas que ya están en las alertas existentes (a menos que sea necesario por alguna razón especial)
4. Para cada alerta que levantes, proporciona:
   - El ID de la regla correspondiente
   - Los datos extraídos según lo especificado en el campo "extractions" de la regla
5. En el campo "reasoning", explica claramente por qué se levanta o no cada alerta

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
            logger.info(f"Reasoning: {analysis.reasoning[:200]}...")
            logger.info(f"Alerts to raise: {len(analysis.alerts)}")
            
            # Procesar y guardar las alertas levantadas
            alerts_raised = 0
            with transaction.atomic():
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
                conversation.save()
            
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
