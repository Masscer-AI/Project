from django.urls import path

from api.compliance.views import PLDEntityListView

app_name = "compliance"

urlpatterns = [
    path("entities/", PLDEntityListView.as_view(), name="pld_entity_list"),
]
