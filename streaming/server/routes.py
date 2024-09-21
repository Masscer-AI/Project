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
    output_path = os.path.join(AUDIO_DIR, "output.mp3")
    await generate_speech_stream(request.text, output_path)
    return FileResponse(output_path, media_type="audio/mpeg", filename="output.mp3")


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
    file_path = os.path.join("streaming", "client", "dist", "index.html")
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


class MessageResponse(BaseModel):
    id: int
    content: str


class ConversationResponse(BaseModel):
    id: int
    user_id: int
    message_count: int

    class Config:
        from_attributes = True


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_user_conversations():
    # user_id = token.user_id
    # conversations = db.query(Conversation).filter(Conversation.user_id == user_id).all()

    # serialized_conversations = []
    # for conversation in conversations:
    #     message_count = len(conversation.messages)
    #     serialized_conversation = ConversationResponse(
    #         id=conversation.id,
    #         user_id=conversation.user_id,
    #         message_count=message_count,
    #     )
    #     serialized_conversations.append(serialized_conversation)

    return "serialized_conversations"


class ConversationDetailResponse(BaseModel):
    id: int
    user_id: int
    messages: List[MessageResponse]

    class Config:
        from_attributes = True


# @router.get(
#     "/conversation/{conversation_id}", response_model=ConversationDetailResponse
# )
# async def get_conversation(
#     conversation_id: int,
#     token: Token = Depends(verify_token),
#     db: Session = Depends(get_db),
# ):
#     conversation = (
#         db.query(Conversation)
#         .filter(
#             Conversation.id == conversation_id, Conversation.user_id == token.user_id
#         )
#         .first()
#     )

#     if not conversation:
#         raise HTTPException(status_code=404, detail="Conversation not found")

#     messages = (
#         db.query(Message).filter(Message.conversation_id == conversation_id).all()
#     )

#     return ConversationDetailResponse(
#         id=conversation.id,
#         user_id=conversation.user_id,
#         messages=[
#             MessageResponse(
#                 id=msg.id, sender=msg.sender, text=msg.text, timestamp=msg.timestamp
#             )
#             for msg in messages
#         ],
#     )


@router.get("/{page_name}", response_class=HTMLResponse)
async def get_page():
    file_path = os.path.join("streaming", "client", "dist", "index.html")
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
    file_path = os.path.join("streaming", "client", "dist", "index.html")
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            html_content = file.read()
        # data = routes_meta.get(page_name, routes_meta["defaults"])

        # for key, value in data.items():
        #     placeholder = f"{{{{{key}}}}}"
        #     html_content = html_content.replace(placeholder, value)

        return HTMLResponse(content=html_content)
    return HTMLResponse(content="Page not found", status_code=404)


