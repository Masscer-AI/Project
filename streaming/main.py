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

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
