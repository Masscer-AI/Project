"""
Vistas HTTP para el servidor MCP y configuración.
"""
import json
import logging
import platform
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from .models import Agent
from .mcp.server import MCPServerHandler
from api.authenticate.decorators.token_required import token_required

logger = logging.getLogger(__name__)


@csrf_exempt
def mcp_server_handler(request, agent_slug):
    """
    Endpoint HTTP para el servidor MCP de un agente específico.
    No requiere autenticación (público) para que Claude Desktop pueda llamarlo.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests are allowed"}, status=405)
    
    return MCPServerHandler.handle_request(request, agent_slug)


@token_required
def get_mcp_config_json(request, agent_slug):
    """
    Genera la configuración JSON para Claude Desktop.
    Requiere autenticación para verificar permisos del agente.
    """
    try:
        user = request.user
        # Verificar que el usuario tiene acceso al agente
        agent = Agent.objects.filter(
            slug=agent_slug
        ).filter(
            Q(user=user) | Q(organization__members__user=user) | Q(is_public=True)
        ).first()
        
        if not agent:
            return JsonResponse({
                "error": "Agent not found or you don't have permission to access it"
            }, status=404)
        
        # Construir URL dinámicamente desde el request
        base_url = request.build_absolute_uri('/').rstrip('/')
        mcp_url = f"{base_url}/v1/ai_layers/mcp/{agent_slug}/"
        
        # Generar configuración HTTP para Claude Desktop
        config = {
            "mcpServers": {
                f"masscer-{agent.slug}": {
                    "url": mcp_url
                }
            }
        }
        
        # Instrucciones según el OS
        os_type = platform.system()
        if os_type == "Darwin":  # macOS
            config_path = "~/Library/Application Support/Claude/claude_desktop_config.json"
        elif os_type == "Windows":
            config_path = "%APPDATA%\\Claude\\claude_desktop_config.json"
        else:  # Linux
            config_path = "~/.config/claude/claude_desktop_config.json"
        
        instructions = (
            f"1. Copy the config_json content below\n"
            f"2. Open or create the file: {config_path}\n"
            f"3. Merge the content into the existing 'mcpServers' object (or create it if it doesn't exist)\n"
            f"4. Save the file and restart Claude Desktop\n"
            f"5. You should see '{agent.name}' available in the connectors menu"
        )
        
        return JsonResponse({
            "config": config,
            "config_json": json.dumps(config, indent=2),
            "agent_name": agent.name,
            "agent_slug": agent.slug,
            "instructions": instructions,
            "config_path": config_path
        })
    
    except Exception as e:
        logger.error(f"Error generating MCP config: {str(e)}", exc_info=True)
        return JsonResponse({
            "error": f"Error generating configuration: {str(e)}"
        }, status=500)

