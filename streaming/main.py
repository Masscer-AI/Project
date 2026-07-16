# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from server.redis_manager import listen_to_notifications

from contextlib import asynccontextmanager
from server.routes import router
from server.socket import sio
from server.mcp.server import handle_streamable_http, mcp_lifespan
from server.mcp.resource_auth import wrap_mcp_app
from server.mcp.oauth_metadata import router as oauth_metadata_router
import socketio
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(listen_to_notifications())
    async with mcp_lifespan():
        yield


app = FastAPI(lifespan=lifespan, redirect_slashes=False)

# OAuth discovery (before MCP mount)
app.include_router(oauth_metadata_router)

# CORS origins from environment variable
origins = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_origins=["*"],
    expose_headers=["Mcp-Session-Id"],
)


class _McpNoRedirectSlashMiddleware:
    """Rewrite /mcp → /mcp/ in-process so clients posting to the resource URL
    (no trailing slash) keep Authorization headers. Starlette Mount would
    otherwise 307-redirect and many clients drop the Bearer token."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path") == "/mcp":
            scope = dict(scope)
            scope["path"] = "/mcp/"
            if scope.get("raw_path") == b"/mcp":
                scope["raw_path"] = b"/mcp/"
        await self.app(scope, receive, send)


# MCP Streamable HTTP — mount before SPA catch-all routes
app.mount("/mcp", wrap_mcp_app(handle_streamable_http))
# Outermost (added last): normalize /mcp before Starlette Mount redirect.
app.add_middleware(_McpNoRedirectSlashMiddleware)

sio_asgi_app = socketio.ASGIApp(socketio_server=sio, other_asgi_app=app)

AUDIO_DIR = "audios"
os.makedirs(AUDIO_DIR, exist_ok=True)

app.include_router(router)
app.mount("/assets", StaticFiles(directory="client/dist/assets"), name="static")
app.add_route("/socket.io/", route=sio_asgi_app, methods=["GET", "POST"])
app.add_websocket_route("/socket.io/", route=sio_asgi_app)

# Widget loader route
from fastapi.responses import Response
from fastapi import Request

@app.get("/widget/{widget_token}.js")
async def widget_loader(widget_token: str, request: Request):
    """
    Serve the widget loader script with the token embedded.
    This script will fetch widget config and initialize the widget.
    FRONTEND_URL first; if unset, uses the request host from the browser.
    """
    frontend_url = os.getenv("FRONTEND_URL", "").rstrip("/")
    if frontend_url:
        base_url = api_url = streaming_server_url = frontend_url
    else:
        base_url = str(request.base_url).rstrip("/")
        # Behind proxy (ngrok, nginx): use X-Forwarded-Proto for correct scheme
        forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
        if forwarded_proto == "https" and base_url.startswith("http://"):
            base_url = "https://" + base_url[7:]
        api_url = base_url
        streaming_server_url = base_url
    
    loader_script = f"""
(function() {{
    'use strict';
    const widgetToken = '{widget_token}';
    const apiUrl = '{api_url}';
    const baseUrl = '{base_url}';
    const streamingUrl = '{streaming_server_url}';
    
    // Set streaming URL for widget to use (must be set before loading widget bundle)
    window.WIDGET_STREAMING_URL = streamingUrl;
    console.log('Widget streaming URL set to:', streamingUrl);
    
    // Fetch widget configuration
    fetch(apiUrl + '/v1/messaging/widgets/' + widgetToken + '/config/')
        .then(response => {{
            if (!response.ok) {{
                throw new Error('Widget not found or disabled');
            }}
            return response.json();
        }})
        .then(config => {{
            const visitorStorageKey = 'masscer_widget_visitor_' + widgetToken;
            const existingVisitorId = localStorage.getItem(visitorStorageKey) || '';
            const sessionUrl = apiUrl + '/v1/messaging/widgets/' + widgetToken + '/session/?visitor_id=' + encodeURIComponent(existingVisitorId);

            return fetch(sessionUrl)
                .then(response => {{
                    if (!response.ok) {{
                        throw new Error('Failed to create widget session');
                    }}
                    return response.json();
                }})
                .then(sessionData => {{
                    if (sessionData.visitor_id) {{
                        localStorage.setItem(visitorStorageKey, sessionData.visitor_id);
                    }}
                    return {{ config, sessionToken: sessionData.token }};
                }});
        }})
        .then(({{ config, sessionToken }}) => {{
            // Set API URL for widget bundle (it runs on file:// or external origins and needs absolute URLs)
            window.WIDGET_API_URL = apiUrl;
            // Load widget bundle
            const script = document.createElement('script');
            // Cache-buster to avoid stale widget bundles in embedded pages
            script.src = baseUrl + '/assets/chat-widget.js?v=' + Date.now();
            script.onload = function() {{
                // Initialize widget - pass streaming URL directly
                if (window.initChatWidget) {{
                    window.initChatWidget(config, sessionToken, widgetToken, streamingUrl);
                }}
            }};
            script.onerror = function() {{
                console.error('Failed to load chat widget bundle');
            }};
            document.head.appendChild(script);
        }})
        .catch(error => {{
            console.error('Error loading chat widget:', error);
        }});
}})();
"""
    return Response(content=loader_script, media_type="application/javascript")

if __name__ == "__main__":
    port = int(os.getenv("FASTAPI_PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
