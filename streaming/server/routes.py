import hashlib
from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Response

from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from server.utils.openai_functions import (
    transcribe_audio,
    generate_speech_stream,
)

import os

router = APIRouter()

SUPPORTED_FORMATS = {
    "flac",
    "m4a",
    "mp3",
    "mp4",
    "mpeg",
    "mpga",
    "oga",
    "ogg",
    "wav",
    "webm",
}
AUDIO_DIR = "audios"


# Definir el modelo de datos para la solicitud de generación de discurso
class SpeechRequest(BaseModel):
    text: str


@router.post("/upload-audio/")
async def upload_audio(file: UploadFile = File(...)):
    if file.content_type.split("/")[1] not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported file format")

    audio_file_path = os.path.join(AUDIO_DIR, file.filename)
    with open(audio_file_path, "wb") as audio_file:
        while contents := await file.read(1024):
            audio_file.write(contents)

    with open(audio_file_path, "rb") as audio_file:
        transcription = transcribe_audio(audio_file)

    return {
        "file_size": os.path.getsize(audio_file_path),
        "transcription": transcription,
    }


@router.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    file_path = os.path.join("client", "dist", "index.html")
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            html_content = file.read()

        return HTMLResponse(content=html_content)
    return HTMLResponse(content="Page not found", status_code=404)


@router.get("/{page_name}", response_class=HTMLResponse)
async def get_page():
    file_path = os.path.join("client", "dist", "index.html")
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            html_content = file.read()
        # data = routes_meta.get(page_name, routes_meta["defaults"])

        # for key, value in data.items():
        #     placeholder = f"{{{{{key}}}}}"
        #     html_content = html_content.replace(placeholder, value)

        return HTMLResponse(content=html_content)
    return HTMLResponse(content="Page not found", status_code=404)


# Simple mapping of file extensions to media types
MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "json": "application/json",
    "txt": "text/plain",
    "html": "text/html",
    "ico": "image/x-icon",
    # Add more as needed
}


@router.get("assets/{asset_name}")
async def get_asset(request: Request, asset_name: str):
    assets_directory = os.path.join("client", "dist", "assets")
    file_path = os.path.join(assets_directory, asset_name)

    if os.path.exists(file_path):
        # Get the file extension
        file_extension = asset_name.split(".")[-1].lower()
        media_type = MEDIA_TYPES.get(
            file_extension, "application/octet-stream"
        )  # Default to binary stream

        with open(file_path, "rb") as file:  # Use "rb" to read binary files
            file_content = file.read()

        return Response(content=file_content, media_type=media_type)

    return Response(status_code=404, content="File not found.")


@router.get("/chat/c/{conversation_id}", response_class=HTMLResponse)
async def get_conversation():
    file_path = os.path.join("client", "dist", "index.html")
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            html_content = file.read()

        return HTMLResponse(content=html_content)
    return HTMLResponse(content="Page not found", status_code=404)


@router.post("/webhook")
async def webhook(request: Request):
    print(await request.json())
    return {"message": "Webhook received"}
