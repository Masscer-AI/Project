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
    ) -> bool:
        """
        Check if a feature flag is enabled for a specific organization or user.

        Priority order:
        1. User-level flag (if exists) - overrides organization-level
        2. Organization-level flag (explicit organization param OR user's organizations)
        3. Role capabilities: if user has an active role in the org and that role lists this flag in capabilities
        4. False (if no assignments exist)

        Args:
            feature_flag_name: The name of the feature flag
            organization: The organization to check the feature flag for (for organization-level flags)
            user: The user to check for user-level feature flags

        Returns:
            bool: True if the feature is enabled for the user or organization, False otherwise
        """
        # Debug logging
        logger.info(f"🔍 is_feature_enabled called: flag={feature_flag_name}, user={user.email if user else None}, org={organization.name if organization else None}")

        # Organization owners get ALL feature flags enabled
        if user is not None:
            is_owner = False
            if organization and organization.owner_id == user.id:
                is_owner = True
            elif Organization.objects.filter(owner=user).exists():
                is_owner = True
            if is_owner:
                logger.info(f"🔍 User {user.email} is an org owner — granting flag '{feature_flag_name}' automatically")
                return True

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
                logger.info(f"🔍 Found user-level assignment: user={user.email}, flag={feature_flag_name}, enabled={user_assignment.enabled}")
                return user_assignment.enabled
            except FeatureFlagAssignment.DoesNotExist:
                logger.info(f"🔍 No user-level assignment found for user={user.email}, flag={feature_flag_name}")
                pass  # No user-level override, check organization level

        # Determine which organization to check (explicit organization param OR user's organizations)
        organization_to_check = organization

        # If no explicit organization, try to get user's organizations
        if not organization_to_check and user:
            # Get organizations where user is owner or member
            owned_orgs = Organization.objects.filter(owner=user)
            # Get organization from user profile
            member_orgs = Organization.objects.none()
            if hasattr(user, 'profile') and user.profile.organization:
                member_orgs = Organization.objects.filter(id=user.profile.organization.id)
            # Combine and get first one (or check all)
            user_organizations = (owned_orgs | member_orgs).distinct()
            
            logger.info(f"🔍 User organizations: user={user.email}, owned={[o.name for o in owned_orgs]}, member={[o.name for o in member_orgs]}")
            
            # Check all user's organizations - if any has it enabled, return True
            for org in user_organizations:
                try:
                    assignment = FeatureFlagAssignment.objects.select_related(
                        "feature_flag"
                    ).get(
                        organization=org,
                        feature_flag__name=feature_flag_name,
                        user__isnull=True,
                    )
                    logger.info(f"🔍 Found org-level assignment: org={org.name}, flag={feature_flag_name}, enabled={assignment.enabled}")
                    if assignment.enabled:
                        return True
                except FeatureFlagAssignment.DoesNotExist:
                    logger.info(f"🔍 No org-level assignment found for org={org.name}, flag={feature_flag_name}")
                    pass
                # Role capabilities: user has feature if any active role in this org has it
                if cls._user_has_capability_via_role(user, org, feature_flag_name):
                    logger.info(f"🔍 Feature enabled via role capability: user={user.email}, org={org.name}, flag={feature_flag_name}")
                    return True

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
                logger.info(f"🔍 Found explicit org assignment: org={organization_to_check.name}, flag={feature_flag_name}, enabled={assignment.enabled}")
                return assignment.enabled
            except FeatureFlagAssignment.DoesNotExist:
                logger.info(f"🔍 No explicit org assignment found for org={organization_to_check.name}, flag={feature_flag_name}")
                pass
            # Role capabilities in explicit org
            if user and cls._user_has_capability_via_role(user, organization_to_check, feature_flag_name):
                logger.info(f"🔍 Feature enabled via role capability: user={user.email}, org={organization_to_check.name}, flag={feature_flag_name}")
                return True

        logger.info(f"🔍 Returning False - no assignment found for flag={feature_flag_name}")
        return False

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

