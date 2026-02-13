import logging
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import FeatureFlag, FeatureFlagAssignment, Organization, RoleAssignment

logger = logging.getLogger(__name__)


class FeatureFlagService:
    """Service for managing and querying feature flags."""

    @classmethod
    def is_feature_enabled(
        cls, feature_flag_name: str, organization: Organization = None, user=None
    ) -> tuple[bool, str]:
        """
        Check if a feature flag is enabled for a specific organization or user.

        Priority order:
        1. Organization owner — all flags enabled automatically
        2. User-level assignment (highest explicit priority)
        3. Organization-level assignment (explicit org param OR user's orgs)
        4. Role capabilities
        5. False (no assignment found)

        Returns:
            (enabled, reason) where reason is one of:
            "is-owner", "direct-user-assignment", "organization-assignment",
            "role-assignment", "not-assigned"
        """

        # Organization owners get ALL feature flags enabled
        if user is not None:
            is_owner = False
            if organization and organization.owner_id == user.id:
                is_owner = True
            elif Organization.objects.filter(owner=user).exists():
                is_owner = True
            if is_owner:
                return True, "is-owner"

        # Check user-level assignment first (highest priority)
        if user is not None:
            try:
                user_assignment = FeatureFlagAssignment.objects.select_related(
                    "feature_flag"
                ).get(
                    user=user,
                    feature_flag__name=feature_flag_name,
                    organization__isnull=True,
                )
                return user_assignment.enabled, "direct-user-assignment"
            except FeatureFlagAssignment.DoesNotExist:
                pass

        # Determine which organization to check
        organization_to_check = organization

        # If no explicit organization, try to get user's organizations
        if not organization_to_check and user:
            owned_orgs = Organization.objects.filter(owner=user)
            member_orgs = Organization.objects.none()
            if hasattr(user, 'profile') and user.profile.organization:
                member_orgs = Organization.objects.filter(id=user.profile.organization.id)
            user_organizations = (owned_orgs | member_orgs).distinct()

            for org in user_organizations:
                try:
                    assignment = FeatureFlagAssignment.objects.select_related(
                        "feature_flag"
                    ).get(
                        organization=org,
                        feature_flag__name=feature_flag_name,
                        user__isnull=True,
                    )
                    if assignment.enabled:
                        return True, "organization-assignment"
                except FeatureFlagAssignment.DoesNotExist:
                    pass
                if cls._user_has_capability_via_role(user, org, feature_flag_name):
                    return True, "role-assignment"

        # Check explicit organization if provided
        if organization_to_check:
            try:
                assignment = FeatureFlagAssignment.objects.select_related(
                    "feature_flag"
                ).get(
                    organization=organization_to_check,
                    feature_flag__name=feature_flag_name,
                    user__isnull=True,
                )
                return assignment.enabled, "organization-assignment"
            except FeatureFlagAssignment.DoesNotExist:
                pass
            if user and cls._user_has_capability_via_role(user, organization_to_check, feature_flag_name):
                return True, "role-assignment"

        return False, "not-assigned"

    @classmethod
    def _user_has_capability_via_role(cls, user, organization, feature_flag_name: str) -> bool:
        """Return True if user has an active role in this organization whose capabilities include the flag."""
        today = timezone.now().date()
        active = RoleAssignment.objects.filter(
            user=user,
            organization=organization,
            from_date__lte=today,
        ).filter(Q(to_date__isnull=True) | Q(to_date__gte=today)).select_related("role")
        for assignment in active:
            caps = assignment.role.capabilities or []
            if feature_flag_name in caps:
                return True
        return False

    @classmethod
    def get_or_create_feature_flag(cls, feature_flag_name: str) -> FeatureFlag:
        """
        Get or create a feature flag by name.

        Args:
            feature_flag_name: The name of the feature flag

        Returns:
            FeatureFlag: The feature flag instance
        """
        feature_flag, created = FeatureFlag.objects.get_or_create(
            name=feature_flag_name
        )
        if created:
            logger.info(f"Created new feature flag: {feature_flag_name}")
        return feature_flag

    @classmethod
    def set_feature_flag(
        cls, feature_flag_name: str, enabled: bool, organization: Organization
    ) -> FeatureFlagAssignment:
        """
        Set a feature flag assignment for an organization.

        Args:
            feature_flag_name: The name of the feature flag
            enabled: Whether the feature should be enabled
            organization: The organization to set the feature flag for

        Returns:
            FeatureFlagAssignment: The created or updated assignment
        """
        with transaction.atomic():
            feature_flag = cls.get_or_create_feature_flag(feature_flag_name)

            assignment, created = FeatureFlagAssignment.objects.update_or_create(
                organization=organization,
                feature_flag=feature_flag,
                defaults={"enabled": enabled, "user": None},
            )

            action = "created" if created else "updated"
            logger.info(
                f"{action.capitalize()} feature flag assignment: {organization.name} - {feature_flag_name} = {enabled}"
            )

            return assignment

    @classmethod
    def get_organization_feature_flags(cls, organization: Organization) -> dict[str, bool]:
        """
        Get all feature flag assignments for an organization.

        Args:
            organization: The organization to get feature flags for

        Returns:
            dict: Dictionary mapping feature flag names to their enabled status
        """
        assignments = FeatureFlagAssignment.objects.select_related(
            "feature_flag"
        ).filter(organization=organization, user__isnull=True)
        return {
            assignment.feature_flag.name: assignment.enabled
            for assignment in assignments
        }

    @classmethod
    def get_feature_flag_organizations(cls, feature_flag_name: str) -> dict[str, bool]:
        """
        Get all organization assignments for a specific feature flag.

        Args:
            feature_flag_name: The name of the feature flag

        Returns:
            dict: Dictionary mapping organization names to their enabled status for this feature
        """
        try:
            feature_flag = FeatureFlag.objects.get(name=feature_flag_name)
            assignments = FeatureFlagAssignment.objects.select_related("organization").filter(
                feature_flag=feature_flag,
                organization__isnull=False,
                user__isnull=True,
            )
            return {
                assignment.organization.name: assignment.enabled for assignment in assignments
            }
        except FeatureFlag.DoesNotExist:
            logger.error(f"Feature flag '{feature_flag_name}' does not exist")
            return {}

    @classmethod
    def ensure_feature_enabled(cls, feature_flag_name: str, organization: Organization) -> bool:
        """
        Ensure a feature flag is enabled for an organization.
        Only creates the assignment if one doesn't already exist (respects intentional disables).

        Returns:
            True if a new assignment was created, False if one already existed.
        """
        feature_flag = cls.get_or_create_feature_flag(feature_flag_name)
        _, created = FeatureFlagAssignment.objects.get_or_create(
            organization=organization,
            feature_flag=feature_flag,
            user=None,
            defaults={"enabled": True},
        )
        if created:
            logger.info(
                f"Auto-enabled feature flag '{feature_flag_name}' for organization '{organization.name}'"
            )
        return created

    @classmethod
    def remove_feature_flag_assignment(cls, feature_flag_name: str, organization: Organization) -> bool:
        """
        Remove a feature flag assignment for an organization.

        Args:
            feature_flag_name: The name of the feature flag
            organization: The organization to remove the assignment for

        Returns:
            bool: True if the assignment was removed, False if it didn't exist
        """
        try:
            assignment = FeatureFlagAssignment.objects.get(
                organization=organization, feature_flag__name=feature_flag_name, user__isnull=True
            )
            assignment.delete()
            logger.info(
                f"Removed feature flag assignment: {organization.name} - {feature_flag_name}"
            )
            return True
        except FeatureFlagAssignment.DoesNotExist:
            logger.error(
                f"Feature flag assignment does not exist: {organization.name} - {feature_flag_name}"
            )
            return False

