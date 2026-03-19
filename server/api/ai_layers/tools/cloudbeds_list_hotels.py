"""
Tool: cloudbeds_list_hotels

Lists the Cloudbeds properties (hotels) connected to the user's organization.
For each connected property it fetches live dashboard data from the Cloudbeds API.

This tool is only available when an organization has completed the Cloudbeds
OAuth flow and has a stored CloudbedsCredential.

Registered in TOOL_REGISTRY as "cloudbeds_list_hotels".
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CloudbedsListHotelsParams(BaseModel):
    """Parameters for the cloudbeds_list_hotels tool (none required)."""

    include_dashboard: bool = Field(
        default=True,
        description=(
            "When true, fetch live dashboard data (occupancy, arrivals, "
            "departures) for each connected property. Set to false for a "
            "faster response with only basic property metadata."
        ),
    )


class HotelInfo(BaseModel):
    property_id: str = Field(description="Cloudbeds property ID.")
    property_name: str = Field(description="Display name of the property.")
    # Dashboard fields (populated when include_dashboard=True)
    occupancy_percent: float | None = Field(None, description="Current occupancy percentage (0-100).")
    total_rooms: int | None = Field(None, description="Total number of rooms.")
    arrivals_today: int | None = Field(None, description="Expected arrivals for today.")
    departures_today: int | None = Field(None, description="Expected departures for today.")
    in_house_guests: int | None = Field(None, description="Number of guests currently in-house.")
    currency: str | None = Field(None, description="Property's default currency code.")


class CloudbedsListHotelsResult(BaseModel):
    hotels: list[HotelInfo] = Field(description="List of connected Cloudbeds properties.")
    total: int = Field(description="Total number of connected properties.")


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------

def _list_hotels_impl(
    *,
    include_dashboard: bool,
    organization_id: int | None,
) -> CloudbedsListHotelsResult:
    from api.cloudbeds.models import CloudbedsCredential
    from api.utils.cloudbeds import CloudBedsIntegration, CloudBedsError

    if not organization_id:
        raise ValueError(
            "cloudbeds_list_hotels requires an organization context. "
            "Make sure the conversation is linked to an organization."
        )

    # Load all credentials for this organization
    # (Currently one-to-one, but modelled as a queryset for forward compatibility)
    credentials = list(
        CloudbedsCredential.objects.filter(organization_id=organization_id)
    )

    if not credentials:
        return CloudbedsListHotelsResult(
            hotels=[],
            total=0,
        )

    hotels: list[HotelInfo] = []

    for cred in credentials:
        try:
            cb = CloudBedsIntegration.from_credential(cred)
        except Exception as exc:
            logger.warning("Could not build CloudBedsIntegration for cred %s: %s", cred.pk, exc)
            continue

        # Basic info from the stored credential
        hotel = HotelInfo(
            property_id=cred.property_id,
            property_name=cred.property_name,
        )

        if include_dashboard:
            try:
                dash = cb.get_dashboard()
                data: dict[str, Any] = dash.get("data", {}) if isinstance(dash, dict) else {}

                hotel.total_rooms = _safe_int(data.get("totalRooms"))
                hotel.arrivals_today = _safe_int(data.get("arrivalsToday") or data.get("checkinsToday"))
                hotel.departures_today = _safe_int(data.get("departuresToday") or data.get("checkoutsToday"))
                hotel.in_house_guests = _safe_int(data.get("inHouseGuests") or data.get("guestsInHouse"))
                hotel.currency = data.get("currencySymbol") or data.get("currency")

                # Occupancy: Cloudbeds may return it directly or we compute it
                raw_occ = data.get("occupancyPercent") or data.get("occupancy")
                if raw_occ is not None:
                    try:
                        hotel.occupancy_percent = float(raw_occ)
                    except (ValueError, TypeError):
                        pass
                elif hotel.total_rooms and hotel.in_house_guests is not None and hotel.total_rooms > 0:
                    hotel.occupancy_percent = round(hotel.in_house_guests / hotel.total_rooms * 100, 1)

            except CloudBedsError as exc:
                logger.warning(
                    "Failed to fetch dashboard for property %s: %s",
                    cred.property_id, exc,
                )
            except Exception as exc:
                logger.exception("Unexpected error fetching dashboard for property %s", cred.property_id)

        hotels.append(hotel)

    return CloudbedsListHotelsResult(hotels=hotels, total=len(hotels))


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------

def get_tool(
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    """
    Return the AgentTool dict for cloudbeds_list_hotels.

    Context args:
        organization_id: The ID of the organization making the request.
                         Resolved automatically from the conversation.
    """

    def cloudbeds_list_hotels(include_dashboard: bool = True) -> CloudbedsListHotelsResult:
        return _list_hotels_impl(
            include_dashboard=include_dashboard,
            organization_id=organization_id,
        )

    return {
        "name": "cloudbeds_list_hotels",
        "description": (
            "List all Cloudbeds hotel properties connected to this organization. "
            "Returns property names, IDs, and optionally live dashboard data "
            "(occupancy, arrivals, departures, in-house guests). "
            "Use this when the user asks about their hotels, properties, or "
            "current hotel occupancy/status. "
            "Requires the organization to have completed the Cloudbeds OAuth connection."
        ),
        "parameters": CloudbedsListHotelsParams,
        "function": cloudbeds_list_hotels,
    }
