#!/usr/bin/env python
"""
Test script for the Cloudbeds integration.

Run inside the Django container:
    python scripts/test_cloudbeds.py --token <access_token>

Or if you already have a credential stored in the DB:
    python scripts/test_cloudbeds.py --org <organization_id>

You can also set CLOUDBEDS_ACCESS_TOKEN in the environment instead of --token.
"""

import argparse
import json
import os
import sys

# ---------------------------------------------------------------------------
# Bootstrap Django
# ---------------------------------------------------------------------------

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")
django.setup()

# ---------------------------------------------------------------------------
# Imports (after django.setup())
# ---------------------------------------------------------------------------

from api.utils.cloudbeds import CloudBedsIntegration, CloudBedsError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pp(label: str, data) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(json.dumps(data, indent=2, default=str))


def _fail(msg: str) -> None:
    print(f"\n[FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"[OK]   {msg}")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_with_token(access_token: str) -> None:
    """Test the CloudBedsIntegration directly using a provided access token."""
    cb = CloudBedsIntegration(access_token=access_token)

    print("\nTesting CloudBedsIntegration with provided access token...\n")

    # 1. Property info
    print("[1/3] Calling get_property_info() ...")
    try:
        info = cb.get_property_info()
        _ok("get_property_info succeeded")
        _pp("Property Info", info)
    except CloudBedsError as exc:
        _fail(f"get_property_info failed: {exc}")

    # 2. Dashboard
    print("\n[2/3] Calling get_dashboard() ...")
    try:
        dash = cb.get_dashboard()
        _ok("get_dashboard succeeded")
        _pp("Dashboard", dash)
    except CloudBedsError as exc:
        print(f"[WARN] get_dashboard failed (may not be in scope): {exc}")

    # 3. List rooms
    print("\n[3/3] Calling list_rooms() ...")
    try:
        rooms = cb.list_rooms()
        _ok("list_rooms succeeded")
        _pp("Rooms", rooms)
    except CloudBedsError as exc:
        print(f"[WARN] list_rooms failed (may not be in scope): {exc}")


def test_with_org(organization_id: int) -> None:
    """Test by loading the stored CloudbedsCredential for the given org."""
    from api.cloudbeds.models import CloudbedsCredential

    print(f"\nLooking up CloudbedsCredential for org_id={organization_id} ...\n")

    try:
        cred = CloudbedsCredential.objects.get(organization_id=organization_id)
    except CloudbedsCredential.DoesNotExist:
        _fail(
            f"No CloudbedsCredential found for org_id={organization_id}.\n"
            "Complete the OAuth flow first: GET /v1/cloudbeds/connect/"
        )
        return

    print(f"  Found credential: property_id={cred.property_id!r}  property_name={cred.property_name!r}")
    print(f"  expires_at={cred.expires_at}  is_expired={cred.is_expired}")

    cb = CloudBedsIntegration.from_credential(cred)
    _ok("Built CloudBedsIntegration from credential (token refreshed if needed)")

    test_with_token(cb.access_token)  # type: ignore[arg-type]


def test_tool(organization_id: int, user_id: int | None = None) -> None:
    """Exercise the actual cloudbeds_list_hotels agent tool."""
    from api.ai_layers.tools.cloudbeds_list_hotels import get_tool

    print(f"\nTesting cloudbeds_list_hotels tool (org={organization_id}, user={user_id}) ...\n")

    tool = get_tool(organization_id=organization_id, user_id=user_id)
    fn = tool["function"]

    try:
        result = fn(include_dashboard=True)
        _ok("cloudbeds_list_hotels succeeded")
        _pp("Result", result.model_dump())
    except ValueError as exc:
        _fail(f"cloudbeds_list_hotels raised ValueError: {exc}")
    except Exception as exc:
        _fail(f"cloudbeds_list_hotels raised unexpected error: {exc}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Test the Cloudbeds integration")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--token",
        help="Cloudbeds access token to test with (skips DB lookup).",
    )
    group.add_argument(
        "--org",
        type=int,
        help="Organization ID whose stored credential to use.",
    )
    parser.add_argument(
        "--user",
        type=int,
        default=None,
        help="User ID to pass as context when testing the agent tool (used for auth check).",
    )
    parser.add_argument(
        "--tool",
        action="store_true",
        help="Also run the cloudbeds_list_hotels agent tool test (requires --org).",
    )
    args = parser.parse_args()

    # Fallback: env var
    token = args.token or os.environ.get("CLOUDBEDS_ACCESS_TOKEN", "")

    if token:
        test_with_token(token)
    elif args.org:
        test_with_org(args.org)
        if args.tool:
            test_tool(args.org, user_id=args.user)
    else:
        parser.print_help()
        print(
            "\nTip: set CLOUDBEDS_ACCESS_TOKEN env var or pass --token / --org.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\nDone.\n")


if __name__ == "__main__":
    main()
