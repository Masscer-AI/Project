import logging
import json
import os
from celery import shared_task
from .actions import generate_conversation_title
from .models import (
    Conversation,
    Message,
    ConversationAlertRule,
    ConversationAlert,
    ScheduledConversationTask,
)
from .schemas import ConversationAnalysisResult
from api.authenticate.models import Organization, FeatureFlag, FeatureFlagAssignment
from api.authenticate.services import FeatureFlagService
from api.utils.openai_functions import create_structured_completion
from api.notify.alert_dispatch import maybe_dispatch_user_notifications
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

SCHEDULER_BASELINE_TOOL_NAMES: list[str] = [
    "read_attachment",
    "list_attachments",
    "generate_document_file",
    "generate_excel_file",
    "send_email",
    "list_organization_members",
    "list_organization_roles",
    "explore_web",
    "rag_query",
]


def _resolve_agent_slugs_for_scheduled_task(task: ScheduledConversationTask) -> list[str]:
    if task.agent_slugs:
        return [str(s) for s in task.agent_slugs if s]

    from api.ai_layers.models import Agent

    meta = task.conversation.metadata or {}
    related = meta.get("related_agents") or []
    agent_ids: list[int] = []
    for item in related:
        if isinstance(item, dict) and item.get("id") is not None:
            try:
                agent_ids.append(int(item["id"]))
            except (TypeError, ValueError):
                continue
    if not agent_ids:
        return []
    agents = Agent.objects.filter(id__in=agent_ids)
    by_id = {a.id: a.slug for a in agents}
    return [by_id[i] for i in agent_ids if i in by_id]


def enqueue_scheduled_conversation_task(task: ScheduledConversationTask) -> str | None:
    """Enqueue Celery ETA for a pending scheduled task; persist celery_task_id."""
    if task.status != ScheduledConversationTask.Status.PENDING or not task.next_run_at:
        return None
    async_result = run_scheduled_conversation_task.apply_async(
        args=[str(task.id)],
        eta=task.next_run_at,
    )
    task.celery_task_id = async_result.id
    task.save(update_fields=["celery_task_id", "updated_at"])
    return async_result.id


@shared_task
def async_generate_conversation_title(conversation_id: str):
    logger.info(
        "async_generate_conversation_title START conversation_id=%s",
        conversation_id,
    )
    try:
        result = generate_conversation_title(conversation_id=conversation_id)
        logger.info(
            "async_generate_conversation_title DONE conversation_id=%s result=%s",
            conversation_id,
            result,
        )
        return result
    except Exception:
        logger.exception(
            "async_generate_conversation_title FAILED conversation_id=%s",
            conversation_id,
        )
        raise


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
    client_datetime: dict | None = None,
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
        client_datetime=client_datetime,
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
        
        api_key = os.environ.get("OPENAI_API_KEY")

        # Obtener alert rules activas y habilitadas de la organización
        alert_rules = ConversationAlertRule.objects.filter(
            organization=organization,
            enabled=True
        ).values('id', 'name', 'trigger', 'extractions')
        
        alert_rules_list = list(alert_rules)
        logger.info(f"Found {len(alert_rules_list)} active alert rules for organization {organization.name}")
        
        # Skip analysis if there are no alert rules
        if not alert_rules_list:
            logger.info(f"Organization {organization.name} has no alert rules, skipping analysis for conversation {conversation_uuid}")
            conversation.pending_analysis = False
            conversation.save(update_fields=['pending_analysis'])
            return {
                "conversation_uuid": conversation_uuid,
                "message_count": message_count,
                "status": "skipped",
                "reason": "No alert rules configured"
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
1. Determinar si debe levantarse alguna alerta según las reglas proporcionadas

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
            logger.info(f"Reasoning: {(analysis.reasoning or '')[:200]}...")
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
                        
                        new_alert = ConversationAlert.objects.create(
                            title=title[:50],  # El campo tiene max_length=50
                            reasoning=analysis.reasoning,
                            extractions=extractions,
                            conversation=conversation,
                            alert_rule=alert_rule,
                            status="PENDING"
                        )
                        maybe_dispatch_user_notifications(new_alert)

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
                conversation.save(update_fields=['pending_analysis'])
            
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


@shared_task
def run_due_scheduled_conversation_tasks():
    """Beat catch-up: enqueue overdue pending scheduled conversation tasks."""
    now = timezone.now()
    due_ids = list(
        ScheduledConversationTask.objects.filter(
            status=ScheduledConversationTask.Status.PENDING,
            next_run_at__lte=now,
        ).values_list("id", flat=True)[:200]
    )
    for task_id in due_ids:
        run_scheduled_conversation_task.delay(str(task_id))
    if due_ids:
        logger.info(
            "run_due_scheduled_conversation_tasks enqueued %d overdue task(s)",
            len(due_ids),
        )
    return {"enqueued": len(due_ids)}


@shared_task
def run_scheduled_conversation_task(scheduled_task_id: str):
    """
    Claim a due ScheduledConversationTask and re-enter conversation_agent_task
    with the stored instruction as a user message.
    """
    from api.ai_layers.tasks import conversation_agent_task
    from api.messaging.schedule_helpers import (
        RECURRING_ADVANCE_EPSILON,
        compute_next_run_at,
    )
    from api.messaging.takeover import is_takeover_active

    from datetime import timedelta

    now = timezone.now()
    with transaction.atomic():
        try:
            task = (
                ScheduledConversationTask.objects.select_for_update()
                .select_related("conversation", "organization", "created_by")
                .get(id=scheduled_task_id)
            )
        except ScheduledConversationTask.DoesNotExist:
            logger.warning(
                "run_scheduled_conversation_task: task %s not found",
                scheduled_task_id,
            )
            return {"status": "error", "error": "not_found"}

        if task.status != ScheduledConversationTask.Status.PENDING:
            return {"status": "skipped", "reason": f"status_{task.status}"}
        if task.next_run_at and task.next_run_at > now:
            return {"status": "skipped", "reason": "not_due"}

        conversation = task.conversation
        if conversation is None or conversation.status == "deleted":
            task.status = ScheduledConversationTask.Status.CANCELLED
            task.last_error = "Conversation missing or deleted"
            task.save(update_fields=["status", "last_error", "updated_at"])
            return {"status": "skipped", "reason": "conversation_unavailable"}

        if is_takeover_active(conversation):
            # Defer without claiming; bump next_run_at to avoid Beat spam.
            task.next_run_at = now + timedelta(minutes=5)
            task.last_error = "Takeover active; deferred"
            task.save(update_fields=["next_run_at", "last_error", "updated_at"])
            logger.info(
                "run_scheduled_conversation_task deferred: takeover active task=%s",
                scheduled_task_id,
            )
            return {"status": "skipped", "reason": "takeover_active"}

        task.status = ScheduledConversationTask.Status.RUNNING
        task.save(update_fields=["status", "updated_at"])

    agent_slugs = _resolve_agent_slugs_for_scheduled_task(task)
    if not agent_slugs:
        task.status = ScheduledConversationTask.Status.FAILED
        task.last_error = "No agent_slugs available for scheduled run"
        task.last_run_at = now
        task.save(update_fields=["status", "last_error", "last_run_at", "updated_at"])
        return {"status": "error", "error": "no_agents"}

    try:
        result = conversation_agent_task(
            conversation_id=str(conversation.id),
            user_inputs=[{"type": "input_text", "text": task.instruction_text}],
            tool_names=list(SCHEDULER_BASELINE_TOOL_NAMES),
            agent_slugs=agent_slugs,
            multiagentic_modality=task.multiagentic_modality or "isolated",
            user_id=task.created_by_id,
            user_message_metadata={
                "source": "scheduled_task",
                "scheduled_task_id": str(task.id),
            },
        )
    except Exception as exc:
        logger.exception(
            "run_scheduled_conversation_task agent failed task=%s",
            scheduled_task_id,
        )
        result = {"status": "error", "error": str(exc)}

    run_finished_at = timezone.now()
    task.last_run_at = run_finished_at
    user_message_id = None
    if isinstance(result, dict):
        user_message_id = result.get("user_message_id")
    if user_message_id is not None:
        task.created_message_id = int(user_message_id)

    agent_status = result.get("status") if isinstance(result, dict) else None
    agent_ok = agent_status == "completed"
    if not agent_ok:
        err = ""
        if isinstance(result, dict):
            err = str(result.get("error") or result.get("reason") or agent_status or "error")
        task.last_error = err[:2000]
        logger.error(
            "run_scheduled_conversation_task incomplete task=%s status=%s error=%s",
            scheduled_task_id,
            agent_status,
            task.last_error,
        )
    else:
        task.last_error = ""

    if task.schedule_type == ScheduledConversationTask.ScheduleType.ONCE:
        task.status = (
            ScheduledConversationTask.Status.DONE
            if agent_ok
            else ScheduledConversationTask.Status.FAILED
        )
        task.celery_task_id = None
        task.save(
            update_fields=[
                "status",
                "last_run_at",
                "last_error",
                "created_message_id",
                "celery_task_id",
                "updated_at",
            ]
        )
        return {"status": task.status, "agent_status": agent_status}

    # Recurring: always advance so one failure does not kill the series.
    try:
        next_run = compute_next_run_at(
            schedule_type="recurring",
            tz_name=task.timezone,
            cron=task.cron,
            after=run_finished_at + RECURRING_ADVANCE_EPSILON,
        )
        task.next_run_at = next_run
        task.status = ScheduledConversationTask.Status.PENDING
        task.save(
            update_fields=[
                "status",
                "next_run_at",
                "last_run_at",
                "last_error",
                "created_message_id",
                "updated_at",
            ]
        )
        enqueue_scheduled_conversation_task(task)
    except Exception as exc:
        logger.exception(
            "run_scheduled_conversation_task failed to advance recurrence task=%s",
            scheduled_task_id,
        )
        task.status = ScheduledConversationTask.Status.FAILED
        task.last_error = (task.last_error + f"; advance_failed: {exc}").strip("; ")[:2000]
        task.save(
            update_fields=[
                "status",
                "last_run_at",
                "last_error",
                "created_message_id",
                "updated_at",
            ]
        )
        return {"status": "failed", "error": "advance_failed"}

    return {
        "status": "completed" if agent_ok else "completed_with_error",
        "agent_status": agent_status,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
    }
