from django.http import JsonResponse
from django.views import View
from .models import Conversation, Message
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    BigConversationSerializer,
)
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from api.authenticate.decorators.token_required import token_required
from .actions import transcribe_audio, generate_speech_api, complete_message
from django.core.files.storage import FileSystemStorage
import os
import uuid
from django.conf import settings


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ConversationView(View):
    def get(self, request, *args, **kwargs):
        user = request.user
        conversation_id = kwargs.get("id")
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, user=user)
                serialized_conversation = BigConversationSerializer(conversation).data
                return JsonResponse(serialized_conversation, safe=False)
            except Conversation.DoesNotExist:
                return JsonResponse(
                    {"message": "Conversation not found", "status": 404}, status=404
                )
        else:
            conversations = Conversation.objects.filter(user=user).order_by(
                "-created_at"
            )

            serialized_conversations = ConversationSerializer(
                conversations, many=True
            ).data
            return JsonResponse(serialized_conversations, safe=False)

    def post(self, request, *args, **kwargs):
        user = request.user

        existing_conversation = Conversation.objects.filter(
            user=user, messages__isnull=True
        ).first()
        if existing_conversation:
            data = BigConversationSerializer(existing_conversation).data
            return JsonResponse(data, status=200)

        conversation = Conversation.objects.create(user=user)
        data = BigConversationSerializer(conversation).data
        return JsonResponse(data, status=201)

    def put(self, request, *args, **kwargs):
        user = request.user
        data = json.loads(request.body)
        conversation_id = kwargs.get("id")
        try:
            Conversation.objects.filter(id=conversation_id, user=user).update(**data)
            updated_conversation = Conversation.objects.get(
                id=conversation_id, user=user
            )
            serialized_data = ConversationSerializer(updated_conversation).data
            return JsonResponse(serialized_data, status=200)
        except Conversation.DoesNotExist:
            return JsonResponse(
                {"message": "Conversation not found", "status": 404}, status=404
            )

    def delete(self, request, *args, **kwargs):
        user = request.user
        conversation_id = kwargs.get("id")
        try:
            Conversation.objects.filter(id=conversation_id, user=user).delete()
            return JsonResponse({"status": "deleted"})
        except Conversation.DoesNotExist:
            return JsonResponse(
                {"message": "Conversation not found", "status": 404}, status=404
            )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class MessageView(View):
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        conversation_id = data.get("conversation")

        if not conversation_id:
            return JsonResponse(
                {"message": "conversation is required", "status": 400}, status=400
            )

        try:
            conversation = Conversation.objects.get(
                id=conversation_id, user=request.user
            )
        except Conversation.DoesNotExist:
            return JsonResponse(
                {"message": "Conversation not found", "status": 404}, status=404
            )

        if not conversation.title and data["type"] == "assistant":
            conversation.generate_title()

        serializer = MessageSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, status=201)
        else:
            return JsonResponse(serializer.errors, status=400)

    def put(self, request, *args, **kwargs):
        data = json.loads(request.body)
        message_id = kwargs.get("id")

        try:
            message = Message.objects.get(
                id=message_id, conversation__user=request.user
            )
        except Message.DoesNotExist:
            return JsonResponse(
                {"message": "Message not found", "status": 404}, status=404
            )

        serializer = MessageSerializer(message, data=data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return JsonResponse({"status": "updated"})
        else:
            return JsonResponse(serializer.errors, status=400)

    def delete(self, request, *args, **kwargs):
        message_id = kwargs.get("id")

        try:
            message = Message.objects.get(
                id=message_id, conversation__user=request.user
            )
            message.delete()
            return JsonResponse({"status": "deleted"})
        except Message.DoesNotExist:
            return JsonResponse(
                {"message": "Message not found", "status": 404}, status=404
            )


@csrf_exempt
def upload_audio(request):
    if request.method == "POST" and request.FILES.get("audio_file"):
        audio_file = request.FILES["audio_file"]

        random_filename = f"{uuid.uuid4()}{os.path.splitext(audio_file.name)[1]}"
        random_filename_speech = f"{uuid.uuid4()}.mp3"

        fs = FileSystemStorage(
            location=os.path.join(settings.MEDIA_ROOT, "audio_files")
        )
        filename = fs.save(random_filename, audio_file)
        file_path = fs.path(filename)

        transcription = transcribe_audio(file_path)

        # Generate speech from the transcription
        # speech_output_path = os.path.join(
        #     settings.MEDIA_ROOT, "audio_files", f"{random_filename_speech}"
        # )
        # audio_data = generate_speech_api(transcription, speech_output_path)

        # with open(speech_output_path, "rb") as audio_file:
        #     audio_data = audio_file.read()
        # print(audio_data, "AUDIO DATA")
        return JsonResponse(
            {
                "transcription": transcription,
                # "speech_audio": audio_data.decode("latin-1"),
            }
        )

    return JsonResponse({"error": "Invalid request"}, status=400)


@csrf_exempt
def get_suggestion(request):
    data = json.loads(request.body) 
    # print(data.get("input"), "INPUT TO GET SUGGESTION")
    suggestion = complete_message(data.get("input"))
    return JsonResponse({"suggestion": suggestion})
