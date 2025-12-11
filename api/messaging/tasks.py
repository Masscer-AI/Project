import logging
import json
from celery import shared_task
from .actions import generate_conversation_title
from .models import Conversation, Message
from .schemas import ConversationAnalysis
from api.authenticate.models import Organization, OrganizationMember, FeatureFlag, FeatureFlagAssignment, CredentialsManager
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
    # Usuarios que son owners
    owner_users = Organization.objects.filter(
        id__in=[org.id for org in organizations]
    ).values_list('owner', flat=True)
    
    # Usuarios que son miembros
    member_users = OrganizationMember.objects.filter(
        organization__in=organizations
    ).values_list('user', flat=True)
    
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
    
    # Buscar si el usuario es miembro de alguna organización
    member_org = OrganizationMember.objects.filter(user=user).select_related('organization').first()
    if member_org:
        return member_org.organization
    
    return None


@shared_task
def analyze_single_conversation(conversation_uuid: str):
    """
    Analiza una conversación individual usando OpenAI con un schema de Pydantic.
    
    Args:
        conversation_uuid: UUID de la conversación a analizar
        
    El análisis incluye: resumen, temas principales, sentimiento, insights clave y elementos de acción.
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
        
        # Obtener la organización del usuario para las credenciales
        organization = get_user_organization(conversation.user)
        
        if not organization:
            logger.warning(f"User {conversation.user} has no organization, using default API key")
            api_key = None  # Usará la del entorno
        else:
            try:
                credentials = CredentialsManager.objects.get(organization=organization)
                api_key = credentials.openai_api_key
                if not api_key:
                    logger.warning(f"Organization {organization.name} has no OpenAI API key, using default")
                    api_key = None
            except CredentialsManager.DoesNotExist:
                logger.warning(f"Organization {organization.name} has no credentials manager, using default API key")
                api_key = None
        
        # Obtener y formatear los mensajes de la conversación
        messages = Message.objects.filter(conversation=conversation).order_by('created_at')
        messages_context = "\n".join(
            [f"{message.type}: {message.text}" for message in messages]
        )
        
        # Crear el prompt del sistema
        system_prompt = """Eres un analista experto de conversaciones. Analiza la siguiente conversación y proporciona:
- Un resumen general y conciso de la conversación
- Los temas principales discutidos
- El sentimiento general (positive, negative, o neutral)
- Insights clave o puntos importantes
- Cualquier elemento de acción, tarea o compromiso mencionado

Sé preciso y objetivo en tu análisis."""
        
        # Realizar el análisis usando OpenAI con el schema de Pydantic
        try:
            analysis = create_structured_completion(
                model="gpt-4o",
                system_prompt=system_prompt,
                user_prompt=messages_context,
                response_format=ConversationAnalysis,
                api_key=api_key,
            )
            
            # Guardar el análisis en el campo summary como JSON
            analysis_dict = analysis.model_dump()
            conversation.summary = json.dumps(analysis_dict, ensure_ascii=False, indent=2)
            conversation.pending_analysis = False
            conversation.save()
            
            logger.info(f"Conversation {conversation_uuid} analysis completed successfully")
            logger.info(f"Analysis summary: {analysis.summary[:100]}...")
            
            return {
                "conversation_uuid": conversation_uuid,
                "message_count": message_count,
                "status": "completed",
                "analysis": analysis_dict
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
        return {
            "conversation_uuid": conversation_uuid,
            "status": "error",
            "error": str(e)
        }
