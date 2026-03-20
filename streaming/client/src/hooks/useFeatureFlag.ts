import { useEffect } from "react";
import {
  FeatureFlagStatusResponse,
  TeamFeatureFlagsResponse,
} from "../modules/apiCalls";
import { useStore } from "../modules/store";

export function useFeatureFlag(featureFlagName: string) {
  const user = useStore((s) => s.user);
  const featureFlags = useStore((s) => s.featureFlags);
  const featureFlagsError = useStore((s) => s.featureFlagsError);
  const ensureFeatureFlags = useStore((s) => s.ensureFeatureFlags);

  useEffect(() => {
    if (!user) return;
    void ensureFeatureFlags();
  }, [user, ensureFeatureFlags]);

  const isLoading = Boolean(
    user && featureFlags === null && !featureFlagsError
  );

  const data: FeatureFlagStatusResponse | null =
    user && featureFlags != null
      ? {
          enabled: featureFlags[featureFlagName] === true,
          feature_flag_name: featureFlagName,
          reason: "client-cache",
        }
      : null;

  return {
    data,
    isLoading,
    error: featureFlagsError,
  };
}

export function useTeamFeatureFlags() {
  const user = useStore((s) => s.user);
  const featureFlags = useStore((s) => s.featureFlags);
  const featureFlagsError = useStore((s) => s.featureFlagsError);
  const ensureFeatureFlags = useStore((s) => s.ensureFeatureFlags);

  useEffect(() => {
    if (!user) return;
    void ensureFeatureFlags();
  }, [user, ensureFeatureFlags]);

  const isLoading = Boolean(
    user && featureFlags === null && !featureFlagsError
  );

  const data: TeamFeatureFlagsResponse | null =
    user && featureFlags != null
      ? { feature_flags: featureFlags }
      : null;

  return { data, isLoading, error: featureFlagsError };
}

/** Clear cached team feature flags (logout already does this; use for permissions-changed later). */
export function invalidateClientFeatureFlagsCache(): void {
  useStore.getState().invalidateFeatureFlags();
}

export function useIsFeatureEnabled(featureFlagName: string): boolean | null {
  const { data, error } = useFeatureFlag(featureFlagName);
  if (error && data == null) {
    return false;
  }
  return data?.enabled ?? null;
}
