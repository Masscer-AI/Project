from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def upload_audio(request):
    if request.method == "POST" and request.FILES["audio_file"]:
        audio_file = request.FILES["audio_file"]
        file_size = audio_file.size
        return JsonResponse({"file_size": file_size})
    return JsonResponse({"error": "Invalid request"}, status=400)
