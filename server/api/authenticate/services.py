import logging
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import FeatureFlag, FeatureFlagAssignment, Organization, RoleAssignment
from .feature_flags_registry import KNOWN_FEATURE_FLAGS

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
        1. Organization owner — registry flags enabled automatically
        2. Direct user-level assignment (highest explicit priority)
        3. Role capabilities (user has an active role whose capabilities include the flag)
        4. Organization-level assignment — ONLY for ``organization_only`` flags
        5. False (no assignment found)

        Note: owners only auto-get flags listed in KNOWN_FEATURE_FLAGS.
        Flags not in the registry require explicit assignment.

        Returns:
            (enabled, reason) where reason is one of:
            "is-owner", "direct-user-assignment", "role-assignment",
            "organization-assignment", "not-assigned"
        """

        # Organization owners get registry feature flags enabled automatically.
        # Flags NOT in KNOWN_FEATURE_FLAGS require explicit assignment.
        if user is not None:
            is_owner = False
            if organization and organization.owner_id == user.id:
                is_owner = True
            elif Organization.objects.filter(owner=user).exists():
                is_owner = True
            if is_owner and feature_flag_name in KNOWN_FEATURE_FLAGS:
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

        # Resolve the user's organizations once
        orgs_to_check = []
        if organization:
            orgs_to_check = [organization]
        elif user:
            owned_orgs = Organization.objects.filter(owner=user)
            member_orgs = Organization.objects.none()
            if hasattr(user, 'profile') and user.profile.organization:
                member_orgs = Organization.objects.filter(id=user.profile.organization.id)
            orgs_to_check = list((owned_orgs | member_orgs).distinct())

        # Check role capabilities (applies to ALL flags)
        if user:
            for org in orgs_to_check:
                if cls._user_has_capability_via_role(user, org, feature_flag_name):
                    return True, "role-assignment"

        # Check organization-level assignment ONLY for organization_only flags
        is_org_only = FeatureFlag.objects.filter(
            name=feature_flag_name, organization_only=True
        ).exists()

        if is_org_only:
            for org in orgs_to_check:
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
    def get_user_role_capabilities(cls, user, organization) -> list[str]:
        """Return the list of feature flag names granted to the user via active roles in this org."""
        today = timezone.now().date()
        active = RoleAssignment.objects.filter(
            user=user,
            organization=organization,
            from_date__lte=today,
        ).filter(Q(to_date__isnull=True) | Q(to_date__gte=today)).select_related("role")
        caps = []
        for assignment in active:
            caps.extend(assignment.role.capabilities or [])
        return caps

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

