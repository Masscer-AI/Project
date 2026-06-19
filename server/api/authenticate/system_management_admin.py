"""System Management admin section.

Reorganizes the Django admin sidebar so that:
  - The custom Organizations Management proxy moves out of the ``Authenticate``
    group into a new ``System Management`` group.
  - A standalone ``Language Settings`` page lives in that same group.

No new Django app or migration is required: we just patch
``AdminSite.get_app_list`` (sidebar/index grouping) and ``AdminSite.get_urls``
(extra admin URL for the language page).
"""

from __future__ import annotations

import re

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.translation import gettext_lazy as _


SYSTEM_MANAGEMENT_LABEL = "system_management"
SYSTEM_MANAGEMENT_NAME = _("System Management")
LANGUAGE_SETTINGS_URL_NAME = "system_management_language_settings"
SQL_CONSOLE_URL_NAME = "system_management_sql_console"
_ORG_PROXY_OBJECT_NAME = "OrganizationManagementProxy"

_FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|REPLACE|MERGE|CALL|EXECUTE|EXEC)\b",
    re.IGNORECASE,
)


def _strip_leading_sql_comments(sql: str) -> str:
    sql = sql.strip()
    while True:
        if sql.startswith("--"):
            end = sql.find("\n")
            sql = sql[end + 1:].strip() if end != -1 else ""
        elif sql.startswith("/*"):
            end = sql.find("*/")
            sql = sql[end + 2:].strip() if end != -1 else ""
        else:
            break
    return sql


def sql_console_view(request):
    user = getattr(request, "user", None)
    if not (user and user.is_active and user.is_staff):
        raise PermissionDenied

    columns = []
    rows = []
    error = None
    query = ""

    if request.method == "POST":
        query = request.POST.get("query", "").strip()
        first_keyword = _strip_leading_sql_comments(query).split()[0].upper() if query.strip() else ""

        if not query:
            error = "Please enter a SQL query."
        elif first_keyword != "SELECT":
            error = "Only SELECT queries are allowed."
        elif _FORBIDDEN_PATTERN.search(query):
            error = "Query contains forbidden keywords (INSERT, UPDATE, DELETE, DROP, etc.)."
        else:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    if cursor.description:
                        columns = [col[0] for col in cursor.description]
                        rows = cursor.fetchmany(500)
            except Exception as exc:
                error = str(exc)

    context = {
        **admin.site.each_context(request),
        "title": _("SQL Console"),
        "opts": None,
        "query": query,
        "columns": columns,
        "rows": rows,
        "error": error,
        "row_count": len(rows),
    }
    request.current_app = admin.site.name
    return TemplateResponse(request, "admin/system_management/sql_console.html", context)


def language_settings_view(request):
    """Dedicated admin page for switching the active language."""
    user = getattr(request, "user", None)
    if not (user and user.is_active and user.is_staff):
        raise PermissionDenied
    context = {
        **admin.site.each_context(request),
        "title": _("Language Settings"),
        "opts": None,
    }
    request.current_app = admin.site.name
    return TemplateResponse(
        request, "admin/system_management/language_settings.html", context
    )


_orig_get_urls = admin.AdminSite.get_urls


def _patched_get_urls(self):
    custom = [
        path(
            "system-management/language/",
            self.admin_view(language_settings_view),
            name=LANGUAGE_SETTINGS_URL_NAME,
        ),
        path(
            "system-management/sql-console/",
            self.admin_view(sql_console_view),
            name=SQL_CONSOLE_URL_NAME,
        ),
    ]
    return custom + _orig_get_urls(self)


admin.AdminSite.get_urls = _patched_get_urls


_orig_get_app_list = admin.AdminSite.get_app_list


def _patched_get_app_list(self, request, app_label=None):
    """Custom admin index that groups Organizations Management + Language Settings under System Management."""
    app_dict = self._build_app_dict(request)

    proxy_entry = None
    auth_app = app_dict.get("authenticate")
    if auth_app:
        kept_models = []
        for m in auth_app.get("models", []):
            if m.get("object_name") == _ORG_PROXY_OBJECT_NAME:
                proxy_entry = m
            else:
                kept_models.append(m)
        auth_app["models"] = kept_models
        if not kept_models:
            app_dict.pop("authenticate", None)

    sysmgmt_models = []
    if proxy_entry:
        sysmgmt_models.append(proxy_entry)

    user = getattr(request, "user", None)
    is_staff = bool(user and user.is_active and user.is_staff)

    lang_url = None
    sql_console_url = None
    if is_staff:
        try:
            lang_url = reverse(f"admin:{LANGUAGE_SETTINGS_URL_NAME}")
        except NoReverseMatch:
            lang_url = None
        try:
            sql_console_url = reverse(f"admin:{SQL_CONSOLE_URL_NAME}")
        except NoReverseMatch:
            sql_console_url = None

    if lang_url:
        sysmgmt_models.append(
            {
                "name": str(_("Language Settings")),
                "object_name": "LanguageSettings",
                "perms": {
                    "add": False,
                    "change": True,
                    "delete": False,
                    "view": True,
                },
                "admin_url": lang_url,
                "view_only": True,
            }
        )

    if sql_console_url:
        sysmgmt_models.append(
            {
                "name": str(_("SQL Console")),
                "object_name": "SqlConsole",
                "perms": {
                    "add": False,
                    "change": True,
                    "delete": False,
                    "view": True,
                },
                "admin_url": sql_console_url,
                "view_only": True,
            }
        )

    if sysmgmt_models:
        app_dict[SYSTEM_MANAGEMENT_LABEL] = {
            "name": str(SYSTEM_MANAGEMENT_NAME),
            "app_label": SYSTEM_MANAGEMENT_LABEL,
            "app_url": sysmgmt_models[0]["admin_url"],
            "has_module_perms": True,
            "models": sysmgmt_models,
        }

    if app_label:
        return [app_dict[app_label]] if app_label in app_dict else []

    # Pin System Management first; other apps stay alphabetically sorted (Django default style).
    apps = list(app_dict.values())
    sysmgmt_app = None
    other_apps: list = []
    for app in apps:
        if app.get("app_label") == SYSTEM_MANAGEMENT_LABEL:
            sysmgmt_app = app
        else:
            other_apps.append(app)
    other_apps.sort(key=lambda x: x["name"].lower())
    app_list = ([sysmgmt_app] if sysmgmt_app is not None else []) + other_apps

    for app in app_list:
        app["models"].sort(key=lambda x: x["name"])
    return app_list


admin.AdminSite.get_app_list = _patched_get_app_list
