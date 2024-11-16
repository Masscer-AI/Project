from django.urls import path

# from .views import LoginAPIView, SignupAPIView, HelloWorldView
from .views import GenerateTrainingDataView, CompletionsView, BulkCompletionView

app_name = "finetuning"

urlpatterns = [
    path("generate/", GenerateTrainingDataView.as_view(), name="generate"),
    path("completions/", CompletionsView.as_view(), name="completions"),
    path(
        "completions/<str:completion_id>/",
        CompletionsView.as_view(),
        name="completions",
    ),
    path("bulk/completions/", BulkCompletionView.as_view(), name="bulk"),
]
