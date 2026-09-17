from __future__ import annotations

import io
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase
from django.utils import timezone

from api.authenticate.models import Organization, Role, RoleAssignment, Token, UserProfile
from api.compliance.watchlists.normalize import fold_text
from api.consumption.models import Currency
from api.org_lists.models import OrganizationList, OrganizationListRecord
from api.org_lists.parse import build_config_from_table, parse_tabular_upload
from api.org_lists.persist import replace_list_records
from api.org_lists.tasks import process_organization_list_import


class ParseCsvTests(SimpleTestCase):
    def test_parse_csv_and_config(self):
        raw = b"id,name,price\n1,Widget,10\n2,,20\n"
        parsed = parse_tabular_upload(raw, filename="products.csv", content_type="text/csv")
        self.assertEqual(parsed["headers"], ["id", "name", "price"])
        self.assertEqual(len(parsed["rows"]), 2)
        self.assertEqual(parsed["rows"][0]["name"], "Widget")
        config = build_config_from_table(parsed["headers"], parsed["rows"])
        by_name = {c["name"]: c for c in config["columns"]}
        self.assertEqual(by_name["name"]["examples"], ["Widget"])
        self.assertTrue(by_name["name"]["can_be_empty"])
        self.assertFalse(by_name["id"]["can_be_empty"])


class PersistTests(TestCase):
    def setUp(self):
        Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
        self.owner = User.objects.create_user(username="list-owner", password="x")
        self.org = Organization.objects.create(name="List Org", owner=self.owner)
        self.org_list = OrganizationList.objects.create(
            organization=self.org,
            name="Test",
            uploaded_by=self.owner,
            original_filename="t.csv",
        )
        self.org_list.file.save(
            "t.csv",
            SimpleUploadedFile("t.csv", b"a,b\n1,2\n3,4\n", content_type="text/csv"),
        )

    def test_replace_list_records(self):
        parsed = parse_tabular_upload(
            b"a,b\n1,2\n3,4\n", filename="t.csv", content_type="text/csv"
        )
        count = replace_list_records(self.org_list, parsed=parsed)
        self.assertEqual(count, 2)
        self.org_list.refresh_from_db()
        self.assertEqual(self.org_list.record_count, 2)
        self.assertEqual(
            self.org_list.import_status, OrganizationList.ImportStatus.SUCCEEDED
        )
        rec = OrganizationListRecord.objects.get(organization_list=self.org_list, position=1)
        self.assertIn(fold_text("1"), rec.search_document)
        replace_list_records(
            self.org_list,
            parsed=parse_tabular_upload(
                b"x,y\n9,8\n", filename="t.csv", content_type="text/csv"
            ),
        )
        self.assertEqual(
            OrganizationListRecord.objects.filter(organization_list=self.org_list).count(),
            1,
        )


class OrgListsApiTests(TestCase):
    def setUp(self):
        Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
        self.client = Client()
        self.owner = User.objects.create_user(username="ol-owner", password="x")
        self.member = User.objects.create_user(username="ol-member", password="x")
        self.outsider = User.objects.create_user(username="ol-outsider", password="x")
        self.org = Organization.objects.create(name="OL Org", owner=self.owner)
        UserProfile.objects.update_or_create(
            user=self.member,
            defaults={"organization": self.org, "is_active": True},
        )
        self.role = Role.objects.create(
            organization=self.org,
            name="KB",
            enabled=True,
            capabilities=["train-agents"],
        )
        RoleAssignment.objects.create(
            user=self.member,
            organization=self.org,
            role=self.role,
            from_date=timezone.now().date(),
        )
        self.owner_token = Token.objects.create(user=self.owner, token_type="permanent")
        self.member_token = Token.objects.create(user=self.member, token_type="permanent")
        self.outsider_token = Token.objects.create(
            user=self.outsider, token_type="permanent"
        )

    def _auth(self, token: Token):
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    @patch("api.org_lists.views.process_organization_list_import.delay")
    def test_owner_can_create_list(self, mock_delay):
        csv_file = SimpleUploadedFile(
            "items.csv", b"id,name\n1,Alpha\n", content_type="text/csv"
        )
        resp = self.client.post(
            f"/v1/org-lists/organizations/{self.org.id}/lists/",
            data={"name": "Items", "description": "Demo", "file": csv_file},
            **_auth(self.owner_token),
        )
        self.assertEqual(resp.status_code, 202)
        body = resp.json()
        self.assertEqual(body["list"]["name"], "Items")
        mock_delay.assert_called_once()

    def test_outsider_forbidden(self):
        resp = self.client.get(
            f"/v1/org-lists/organizations/{self.org.id}/lists/",
            **_auth(self.outsider_token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_member_without_train_agents_forbidden(self):
        self.role.capabilities = []
        self.role.save()
        resp = self.client.get(
            f"/v1/org-lists/organizations/{self.org.id}/lists/",
            **_auth(self.member_token),
        )
        self.assertEqual(resp.status_code, 403)


class ImportTaskTests(TestCase):
    def setUp(self):
        Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
        self.owner = User.objects.create_user(username="task-owner", password="x")
        self.org = Organization.objects.create(name="Task Org", owner=self.owner)
        self.org_list = OrganizationList.objects.create(
            organization=self.org,
            name="Import me",
            uploaded_by=self.owner,
            original_filename="data.csv",
        )
        self.org_list.file.save(
            "data.csv",
            SimpleUploadedFile(
                "data.csv",
                b"sku,title\nA1,First\n",
                content_type="text/csv",
            ),
        )

    def test_process_import_succeeds(self):
        result = process_organization_list_import(str(self.org_list.id))
        self.assertEqual(result["status"], "succeeded")
        self.org_list.refresh_from_db()
        self.assertEqual(self.org_list.import_status, OrganizationList.ImportStatus.SUCCEEDED)
        self.assertEqual(self.org_list.record_count, 1)
