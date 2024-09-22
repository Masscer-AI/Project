import hashlib
from fastapi import APIRouter, File, UploadFile, HTTPException, Request

from pydantic import BaseModel
from fastapi.responses import FileResponse, HTMLResponse
from server.utils.openai_functions import (
    transcribe_audio,
    generate_speech_stream,
    generate_image,
)
from server.utils.ollama_functions import list_ollama_models

import os
from typing import List

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


@router.post("/generate_speech/")
async def generate_speech(request: SpeechRequest):
    text = request.text  # Accede a la propiedad 'text' del objeto JSON
    # Hash the text to obtain a unique value
    hashed_text = hashlib.md5(text.encode()).hexdigest()

    # Save the output path using the hash as the name
    output_path = os.path.join(AUDIO_DIR, f"{hashed_text}.mp3")
    await generate_speech_stream(request.text, output_path)
    
    # Devuelve un JSON con la información del archivo
    return {"file_path": output_path, "file_name": f"{hashed_text}.mp3"}


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


class ImageRequest(BaseModel):
    prompt: str


@router.post("/generate_image/")
async def generate_image_route(request: ImageRequest):
    try:
        image_url = generate_image(request.prompt)
        return {"image_url": image_url}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"message": str(e), "status": "error", "type": "GenerationError"},
        )


@router.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    print("Hello")
    file_path = os.path.join("client", "dist", "index.html")
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            html_content = file.read()

        return HTMLResponse(content=html_content)
    return HTMLResponse(content="Page not found", status_code=404)


@router.get("/get-models")
async def get_models():
    # print("models")
    models = list_ollama_models()
    # print(models)
    return models


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


@router.get("/chat/c/{conversation_id}", response_class=HTMLResponse)
async def get_conversation():
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
