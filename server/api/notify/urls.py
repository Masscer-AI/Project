from django.urls import path
from api.notify.views import NotificationRuleView

urlpatterns = [
    path("notification-rules/", NotificationRuleView.as_view(), name="notification_rule_list"),
    path("notification-rules/<uuid:id>/", NotificationRuleView.as_view(), name="notification_rule_detail"),
]
