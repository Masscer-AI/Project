import logging
from django.db import transaction
from django.db.models import Q

from .models import FeatureFlag, FeatureFlagAssignment, Organization, OrganizationMember

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
        3. False (if no assignments exist)

        Args:
            feature_flag_name: The name of the feature flag
            organization: The organization to check the feature flag for (for organization-level flags)
            user: The user to check for user-level feature flags

        Returns:
            bool: True if the feature is enabled for the user or organization, False otherwise
        """
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
                return user_assignment.enabled
            except FeatureFlagAssignment.DoesNotExist:
                pass  # No user-level override, check organization level

        # Determine which organization to check (explicit organization param OR user's organizations)
        organization_to_check = organization

        # If no explicit organization, try to get user's organizations
        if not organization_to_check and user:
            # Get organizations where user is owner or member
            owned_orgs = Organization.objects.filter(owner=user)
            member_orgs = Organization.objects.filter(
                organizationmember__user=user
            )
            # Combine and get first one (or check all)
            user_organizations = (owned_orgs | member_orgs).distinct()
            
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
                    if assignment.enabled:
                        return True
                except FeatureFlagAssignment.DoesNotExist:
                    continue

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
                return assignment.enabled
            except FeatureFlagAssignment.DoesNotExist:
                pass

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

