from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api.ai_layers.models import LanguageModel
from api.authenticate.models import Organization, Role, RoleAssignment, Token, UserProfile
from api.compliance.models import (
    WatchlistListSlug,
    WatchlistRecord,
    WatchlistSnapshot,
    WatchlistSnapshotStatus,
)
from api.compliance.watchlists.normalize import fold_text
from api.consumption.models import Currency
from api.providers.models import AIProvider


def _bootstrap():
    Currency.objects.get_or_create(
        name="Compute Unit", defaults={"one_usd_is": 1000}
    )
    provider, _ = AIProvider.objects.get_or_create(name="OpenAI-watchlist-api")
    LanguageModel.objects.get_or_create(
        slug="gpt-watchlist-api",
        defaults={"provider": provider, "name": "GPT Watchlist API"},
    )


def _snapshot(slug, *, current, count, generated, name, reference, raw=None):
    snap = WatchlistSnapshot.objects.create(
        list_slug=slug,
        source_url="https://example.test/list.csv",
        file_sha256=f"{slug}-{current}-{reference}",
        date_generated=generated,
        status=WatchlistSnapshotStatus.SUCCEEDED,
        is_current=current,
        record_count=count,
    )
    WatchlistRecord.objects.create(
        snapshot=snap,
        record_type="entity",
        reference_number=reference,
        primary_name=name,
        listed_on="06/11/2026",
        search_document=fold_text(f"{reference} {name}"),
        raw=raw or {},
    )


class WatchlistCatalogApiTests(TestCase):
    def setUp(self):
        _bootstrap()
        self.owner = User.objects.create_user(
            username="watchlist-owner",
            email="watchlist-owner@test.com",
            password="x",
        )
        self.org = Organization.objects.create(
            name="Watchlist Org",
            owner=self.owner,
            pld_access_enabled=True,
        )
        UserProfile.objects.update_or_create(
            user=self.owner,
            defaults={"organization": self.org},
        )
        self.token = Token.objects.create(user=self.owner)
        self.client = APIClient()
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}
        _snapshot(
            WatchlistListSlug.SAT_69B,
            current=False,
            count=1,
            generated="01/01/2020",
            name="Vieja SA",
            reference="VIE010101AAA",
        )
        _snapshot(
            WatchlistListSlug.SAT_69B,
            current=True,
            count=14820,
            generated="06/11/2026",
            name="Taller del Norte SA",
            reference="TAN010101AAA",
            raw={"situacion del contribuyente": "Definitivo"},
        )
        _snapshot(
            WatchlistListSlug.SAT_69_FIRMES,
            current=True,
            count=40,
            generated="02/11/2026",
            name="Creditos Firmes SA",
            reference="FIR010101AAA",
        )

    def test_catalog_shows_current_lists_only(self):
        response = self.client.get("/v1/compliance/watchlists/", **self.auth)
        self.assertEqual(response.status_code, 200)
        rows = {row["list_slug"]: row for row in response.json()["results"]}
        self.assertEqual(set(rows), set(WatchlistListSlug.values))
        current = rows[WatchlistListSlug.SAT_69B]
        self.assertEqual(current["record_count"], 14820)
        self.assertEqual(current["date_generated"], "06/11/2026")
        self.assertTrue(current["ingested_at"])
        self.assertEqual(rows[WatchlistListSlug.ONU_CSNU]["record_count"], 0)
        self.assertIsNone(rows[WatchlistListSlug.ONU_CSNU]["ingested_at"])

    def test_name_search_uses_the_current_list(self):
        response = self.client.get(
            "/v1/compliance/watchlists/search/",
            {"q": "Taller Norte"},
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["truncated"])
        self.assertEqual(len(body["results"]), 1)
        hit = body["results"][0]
        self.assertEqual(hit["primary_name"], "Taller del Norte SA")
        self.assertEqual(hit["reference_number"], "TAN010101AAA")
        self.assertEqual(hit["situation"], "Definitivo")
        self.assertEqual(hit["list_slug"], WatchlistListSlug.SAT_69B)

    def test_name_on_an_rfc_list_needs_that_list(self):
        missed = self.client.get(
            "/v1/compliance/watchlists/search/",
            {"q": "Creditos Firmes"},
            **self.auth,
        )
        self.assertEqual(missed.status_code, 200)
        self.assertEqual(missed.json()["results"], [])
        found = self.client.get(
            "/v1/compliance/watchlists/search/",
            {"q": "Creditos Firmes", "list": WatchlistListSlug.SAT_69_FIRMES},
            **self.auth,
        )
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json()["results"][0]["reference_number"], "FIR010101AAA")

    def test_rfc_search_checks_every_sat_list(self):
        response = self.client.get(
            "/v1/compliance/watchlists/search/",
            {"q": "FIR010101AAA"},
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["results"][0]["list_slug"],
            WatchlistListSlug.SAT_69_FIRMES,
        )

    def test_short_or_unknown_list_is_rejected(self):
        short = self.client.get(
            "/v1/compliance/watchlists/search/",
            {"q": "ab"},
            **self.auth,
        )
        self.assertEqual(short.status_code, 400)
        self.assertEqual(short.json()["error"], "invalid-query")
        unknown = self.client.get(
            "/v1/compliance/watchlists/search/",
            {"q": "Taller Norte", "list": "not-a-list"},
            **self.auth,
        )
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(unknown.json()["error"], "unknown-list")

    def test_member_without_compliance_access_is_blocked(self):
        member = User.objects.create_user(
            username="watchlist-member",
            email="watchlist-member@test.com",
            password="x",
        )
        UserProfile.objects.update_or_create(
            user=member,
            defaults={"organization": self.org, "is_active": True},
        )
        token = Token.objects.create(user=member)
        response = self.client.get(
            "/v1/compliance/watchlists/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(response.status_code, 404)

    def test_member_with_compliance_access_can_read_the_catalog(self):
        member = User.objects.create_user(
            username="watchlist-compliance",
            email="watchlist-compliance@test.com",
            password="x",
        )
        UserProfile.objects.update_or_create(
            user=member,
            defaults={"organization": self.org, "is_active": True},
        )
        role = Role.objects.create(
            organization=self.org,
            name="Compliance lists",
            enabled=True,
            capabilities=["organization-compliance-access"],
        )
        RoleAssignment.objects.create(
            user=member,
            organization=self.org,
            role=role,
            from_date=timezone.now().date(),
        )
        token = Token.objects.create(user=member)
        response = self.client.get(
            "/v1/compliance/watchlists/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(response.status_code, 200)
