from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.assignments.actions import create_user_assignment, ensure_owner_onboarding
from api.assignments.models import AssignmentStatus, UserAssignment
from api.assignments.schemas import build_metadata_from_steps
from api.assignments.services import update_assignment_step_status
from api.authenticate.models import Organization, Token, UserProfile


class AssignmentSchemaTests(TestCase):
    def test_build_metadata_assigns_ids_and_order(self):
        meta = build_metadata_from_steps(
            [
                {"title": "Invite team"},
                {"title": "Create agent", "app_url": "/chat"},
            ]
        )
        self.assertEqual(len(meta["steps"]), 2)
        self.assertEqual(meta["steps"][0]["order"], 1)
        self.assertEqual(meta["steps"][0]["status"], "pending")
        self.assertEqual(meta["steps"][0]["id"], "invite_team")

    def test_duplicate_titles_get_unique_ids(self):
        meta = build_metadata_from_steps(
            [
                {"title": "Step one"},
                {"title": "Step one"},
            ]
        )
        ids = [s["id"] for s in meta["steps"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_navigate_button_resolves_route(self):
        meta = build_metadata_from_steps(
            [
                {
                    "title": "Invite",
                    "button": {
                        "text": "Open members",
                        "action_type": "navigate",
                        "action_target": "organization_members",
                    },
                }
            ]
        )
        step = meta["steps"][0]
        self.assertEqual(step["route"], "/organization?activeTab=members")
        self.assertEqual(step["button"]["action_type"], "navigate")

    def test_focus_button_resolves_route(self):
        meta = build_metadata_from_steps(
            [
                {
                    "title": "Agents",
                    "button": {
                        "text": "Highlight",
                        "action_type": "focus_element",
                        "action_target": "agents-modal-trigger",
                    },
                }
            ]
        )
        step = meta["steps"][0]
        self.assertEqual(step["route"], "/chat")
        self.assertEqual(step["button"]["action_type"], "focus_element")

    def test_invalid_navigate_target_raises(self):
        with self.assertRaises(ValueError):
            build_metadata_from_steps(
                [
                    {
                        "title": "Bad",
                        "button": {
                            "text": "Go",
                            "action_type": "navigate",
                            "action_target": "nonexistent_page",
                        },
                    }
                ]
            )

    def test_invalid_focus_target_raises(self):
        with self.assertRaises(ValueError):
            build_metadata_from_steps(
                [
                    {
                        "title": "Bad",
                        "button": {
                            "text": "Go",
                            "action_type": "focus_element",
                            "action_target": "made-up-selector",
                        },
                    }
                ]
            )

    def test_legacy_app_url_becomes_navigate_button(self):
        meta = build_metadata_from_steps(
            [{"title": "Legacy", "app_url": "/chat"}]
        )
        step = meta["steps"][0]
        self.assertEqual(step["button"]["action_type"], "navigate")
        self.assertEqual(step["route"], "/chat")


class UserAssignmentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="assignuser", email="assign@test.com", password="pass12345"
        )

    def test_create_assignment_persists_valid_metadata(self):
        meta = build_metadata_from_steps([{"title": "Do something"}])
        a = UserAssignment.objects.create(
            user=self.user,
            title="My task",
            metadata=meta,
        )
        self.assertEqual(a.parsed_metadata().steps[0].title, "Do something")


class AssignmentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="svcuser", email="svc@test.com", password="pass12345"
        )
        meta = build_metadata_from_steps(
            [
                {"title": "First", "id": "first"},
                {"title": "Second", "id": "second"},
            ]
        )
        self.assignment = UserAssignment.objects.create(
            user=self.user,
            title="Workflow",
            metadata=meta,
        )

    def test_mark_step_done_updates_assignment_status(self):
        update_assignment_step_status(self.assignment, "first", "done")
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, AssignmentStatus.IN_PROGRESS)

        update_assignment_step_status(self.assignment, "second", "done")
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, AssignmentStatus.DONE)
        self.assertIsNotNone(self.assignment.completed_at)


class EnsureOwnerOnboardingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@test.com", password="pass12345"
        )
        self.other = User.objects.create_user(
            username="other", email="other@test.com", password="pass12345"
        )
        self.org = Organization.objects.create(name="Test Org", owner=self.owner)
        UserProfile.objects.create(user=self.owner, organization=self.org)

    def test_ensure_owner_onboarding_idempotent(self):
        a1, created1 = ensure_owner_onboarding(self.owner, self.org)
        a2, created2 = ensure_owner_onboarding(self.owner, self.org)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(a1.id, a2.id)
        self.assertEqual(a1.key, "owner_onboarding")
        self.assertEqual(len(a1.parsed_metadata().steps), 3)

    def test_ensure_owner_onboarding_skips_non_owner(self):
        result, created = ensure_owner_onboarding(self.other, self.org)
        self.assertIsNone(result)
        self.assertFalse(created)


class CreateUserAssignmentToolTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tooluser", email="tool@test.com", password="pass12345"
        )

    def test_create_user_assignment_impl(self):
        from api.ai_layers.tools.create_user_assignment import _create_user_assignment_impl

        result = _create_user_assignment_impl(
            "Onboarding",
            [{"title": "Step A"}, {"title": "Step B", "app_url": "/chat"}],
            user_id=self.user.id,
        )
        self.assertEqual(len(result.steps), 2)
        self.assertTrue(
            UserAssignment.objects.filter(user=self.user, title="Onboarding").exists()
        )


class UserAssignmentAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="apiuser", email="api@test.com", password="pass12345"
        )
        self.token, _ = Token.objects.get_or_create(user=self.user, token_type="login")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        meta = build_metadata_from_steps([{"title": "API step", "id": "api_step"}])
        self.assignment = UserAssignment.objects.create(
            user=self.user,
            title="API workflow",
            metadata=meta,
        )

    def test_list_assignments(self):
        res = self.client.get("/v1/assignments/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["assignments"]), 1)

    def test_patch_step_marks_done(self):
        url = f"/v1/assignments/{self.assignment.id}/steps/api_step/"
        res = self.client.patch(url, {"status": "done"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "done")
