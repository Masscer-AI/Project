from django.urls import path

# from .views import LoginAPIView, SignupAPIView, HelloWorldView
from .views import GenerateTrainingDataView

app_name = "finetuning"

urlpatterns = [
    path("generate/", GenerateTrainingDataView.as_view(), name="generate"),
]
