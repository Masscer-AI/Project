from django.contrib import admin
from django.test import SimpleTestCase
from django.urls import reverse

from api.authenticate.system_management_admin import (
    LANGUAGE_SETTINGS_URL_NAME,
    SYSTEM_MANAGEMENT_LABEL,
)


class OrganizationManagementI18nRoutingTests(SimpleTestCase):
    def test_set_language_named_route(self):
        self.assertEqual(reverse("set_language"), "/i18n/setlang/")

    def test_admin_language_settings_named_route(self):
        self.assertEqual(
            reverse(f"admin:{LANGUAGE_SETTINGS_URL_NAME}"),
            "/admin/system-management/language/",
        )


class SystemManagementAdminAppListTests(SimpleTestCase):
    """Sidebar grouping: Organizations Management lives under System Management."""

    class _FakeUser:
        is_active = True
        is_staff = True
        is_superuser = True

        def has_perm(self, _perm):
            return True

        def has_perms(self, _perms):
            return True

        def has_module_perms(self, _label):
            return True

    class _FakeRequest:
        def __init__(self):
            self.user = SystemManagementAdminAppListTests._FakeUser()
            self.path = "/admin/"

    def test_get_app_list_groups_org_mgmt_and_language_under_system_management(self):
        request = self._FakeRequest()
        app_list = admin.site.get_app_list(request)
        labels = {a["app_label"]: a for a in app_list}
        self.assertIn(SYSTEM_MANAGEMENT_LABEL, labels)
        sysmgmt = labels[SYSTEM_MANAGEMENT_LABEL]
        names = {m["object_name"] for m in sysmgmt["models"]}
        self.assertIn("OrganizationManagementProxy", names)
        self.assertIn("LanguageSettings", names)
        auth = labels.get("authenticate")
        if auth:
            auth_names = {m["object_name"] for m in auth["models"]}
            self.assertNotIn("OrganizationManagementProxy", auth_names)

    def test_system_management_is_first_in_app_list(self):
        request = self._FakeRequest()
        app_list = admin.site.get_app_list(request)
        labels = [a["app_label"] for a in app_list]
        if SYSTEM_MANAGEMENT_LABEL in labels:
            self.assertEqual(labels[0], SYSTEM_MANAGEMENT_LABEL)
