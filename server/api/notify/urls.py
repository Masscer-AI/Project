from django.urls import path
from api.notify.views import NotificationRuleView, UserNotificationView

app_name = "notify"

urlpatterns = [
    path("notification-rules/", NotificationRuleView.as_view(), name="notification_rule_list"),
    path("notification-rules/<uuid:id>/", NotificationRuleView.as_view(), name="notification_rule_detail"),
    path("my-notifications/", UserNotificationView.as_view(), name="user_notification_list"),
    path(
        "my-notifications/<uuid:id>/",
        UserNotificationView.as_view(),
        name="user_notification_detail",
    ),
]
