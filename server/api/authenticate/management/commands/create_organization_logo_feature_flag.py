from django.core.management.base import BaseCommand
from api.authenticate.services import FeatureFlagService


class Command(BaseCommand):
    help = "Create the 'manage-organization' feature flag if it doesn't exist"

    def handle(self, *args, **options):
        feature_flag_name = "manage-organization"
        
        # Get or create the feature flag
        feature_flag = FeatureFlagService.get_or_create_feature_flag(feature_flag_name)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Feature flag "{feature_flag_name}" is ready (ID: {feature_flag.id})'
            )
        )
        self.stdout.write(
            self.style.WARNING(
                '\nNote: To enable this feature flag for an organization or user, '
                'you need to create a FeatureFlagAssignment in the Django admin or via the API.'
            )
        )

