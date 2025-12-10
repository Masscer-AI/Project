import logging
from celery import shared_task
from .actions import generate_conversation_title
from .models import Conversation, Message
from api.authenticate.models import Organization, OrganizationMember, FeatureFlag, FeatureFlagAssignment
from api.authenticate.services import FeatureFlagService
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


@shared_task
def analyze_single_conversation(conversation_uuid: str):
    """
    Analiza una conversación individual.
    
    Args:
        conversation_uuid: UUID de la conversación a analizar
        
    Por ahora solo imprime el número de mensajes y setea pending_analysis como False.
    """
    try:
        conversation = Conversation.objects.get(id=conversation_uuid)
        
        # Contar mensajes
        message_count = Message.objects.filter(conversation=conversation).count()
        
        logger.info(f"Analyzing conversation {conversation_uuid}: {message_count} messages to analyze")
        
        # Setear pending_analysis como False
        conversation.pending_analysis = False
        conversation.save()
        
        logger.info(f"Conversation {conversation_uuid} analysis completed, pending_analysis set to False")
        
        return {
            "conversation_uuid": conversation_uuid,
            "message_count": message_count,
            "status": "completed"
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
