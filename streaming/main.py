# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
from contextlib import asynccontextmanager
from server.routes import router
from server.socket import sio_asgi_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    # await database.connect()
    yield
    # await database.disconnect()


app = FastAPI(lifespan=lifespan)

AUDIO_DIR = "audios"

os.makedirs(AUDIO_DIR, exist_ok=True)

app.include_router(router)

app.mount("/assets", StaticFiles(directory="client/dist/assets"), name="static")


app.add_route("/socket.io/", route=sio_asgi_app, methods=["GET", "POST"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
