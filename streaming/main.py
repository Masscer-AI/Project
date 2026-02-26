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
import socketio
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    # await database.connect()
    asyncio.create_task(listen_to_notifications())
    yield

    # await database.disconnect()


app = FastAPI(lifespan=lifespan)

# CORS origins from environment variable
origins = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origins=["*"],
)


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
    """
    base_url = str(request.base_url).rstrip("/")
    api_url = os.getenv("API_URL", "http://localhost:8000")
    streaming_server_url = os.getenv("STREAMING_SERVER_URL", base_url)
    
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
            // Load widget bundle
            const script = document.createElement('script');
            script.src = baseUrl + '/assets/chat-widget.js';
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
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)
