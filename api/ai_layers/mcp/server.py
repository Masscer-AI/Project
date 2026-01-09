"""
Handler para el servidor MCP HTTP.
Maneja las peticiones JSON-RPC del protocolo MCP.
"""
import json
import logging
from typing import Any, Dict
from django.http import JsonResponse
from ..models import Agent

logger = logging.getLogger(__name__)


class MCPServerHandler:
    """Maneja las peticiones del protocolo MCP"""
    
    @staticmethod
    def handle_request(request, agent_slug: str) -> JsonResponse:
        """Procesa una petición MCP JSON-RPC"""
        try:
            body = json.loads(request.body)
            method = body.get("method")
            params = body.get("params", {})
            request_id = body.get("id")
            
            # Verificar que el agente existe
            try:
                agent = Agent.objects.get(slug=agent_slug)
            except Agent.DoesNotExist:
                return JsonResponse({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": f"Agent '{agent_slug}' not found"
                    }
                }, status=404)
            
            # Enrutar según el método
            if method == "initialize":
                return MCPServerHandler._handle_initialize(params, request_id)
            elif method == "tools/list":
                return MCPServerHandler._handle_tools_list(params, request_id, agent)
            elif method == "tools/call":
                return MCPServerHandler._handle_tools_call(params, request_id, agent)
            else:
                return JsonResponse({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error: Invalid JSON"
                }
            }, status=400)
        except Exception as e:
            logger.error(f"MCP server error: {str(e)}", exc_info=True)
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": body.get("id") if 'body' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }, status=500)
    
    @staticmethod
    def _handle_initialize(params: Dict[str, Any], request_id: Any) -> JsonResponse:
        """Maneja el método initialize del protocolo MCP"""
        return JsonResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "masscer-agent-mcp",
                    "version": "1.0.0"
                }
            }
        })
    
    @staticmethod
    def _handle_tools_list(params: Dict[str, Any], request_id: Any, agent: Agent) -> JsonResponse:
        """Lista las herramientas disponibles (el agente)"""
        tool = {
            "name": f"masscer_agent_{agent.slug}",
            "description": (
                f"Interact with Masscer agent '{agent.name}'. "
                f"{agent.act_as[:200] if agent.act_as else 'AI assistant powered by Masscer.'}"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message or question to send to the agent"
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional context or background information to provide to the agent",
                        "default": ""
                    }
                },
                "required": ["message"]
            }
        }
        
        return JsonResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [tool]
            }
        })
    
    @staticmethod
    def _handle_tools_call(params: Dict[str, Any], request_id: Any, agent: Agent) -> JsonResponse:
        """Ejecuta una llamada a la herramienta (agente)"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name.startswith(f"masscer_agent_{agent.slug}"):
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32602,
                    "message": f"Invalid tool name: {tool_name}"
                }
            }, status=400)
        
        message = arguments.get("message", "")
        context = arguments.get("context", "")
        
        if not message:
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32602,
                    "message": "Missing required parameter: message"
                }
            }, status=400)
        
        try:
            # Llamar al agente
            response = agent.answer(
                context=context,
                user_message=message,
            )
            
            # Extraer el texto de respuesta
            if hasattr(response, 'example'):
                response_text = response.example
            elif isinstance(response, dict):
                response_text = json.dumps(response, indent=2, ensure_ascii=False)
            elif hasattr(response, 'model_dump'):
                response_text = json.dumps(response.model_dump(), indent=2, ensure_ascii=False)
            else:
                response_text = str(response)
            
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": response_text
                        }
                    ]
                }
            })
        except Exception as e:
            logger.error(f"Error calling agent {agent.slug}: {str(e)}", exc_info=True)
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error executing agent: {str(e)}"
                }
            }, status=500)

