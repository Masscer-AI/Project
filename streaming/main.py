# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from contextlib import asynccontextmanager
from server.routes import router
from server.socket import sio
import socketio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # await database.connect()
    yield
    # await database.disconnect()

app = FastAPI(lifespan=lifespan)

# CORS origins from environment variable
origins = os.getenv("CORS_ORIGINS", "*").split(",")
print(origins, "ORIGINS")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origins=["*"],
)

# # Custom middleware to add Access-Control-Allow-Private-Network header
# @app.middleware("http")
# async def add_private_network_header(request, call_next):
#     response = await call_next(request)
#     response.headers["Access-Control-Allow-Private-Network"] = "true"
#     return response

sio_asgi_app = socketio.ASGIApp(socketio_server=sio, other_asgi_app=app)

AUDIO_DIR = "audios"
os.makedirs(AUDIO_DIR, exist_ok=True)

app.include_router(router)
app.mount("/assets", StaticFiles(directory="client/dist/assets"), name="static")
app.add_route("/socket.io/", route=sio_asgi_app, methods=["GET", "POST"])
app.add_websocket_route("/socket.io/", route=sio_asgi_app)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
