import { useState, useEffect } from "react";
import { checkFeatureFlag, getTeamFeatureFlags, FeatureFlagStatusResponse, TeamFeatureFlagsResponse } from "../modules/apiCalls";
import { useStore } from "../modules/store";

export function useFeatureFlag(featureFlagName: string) {
  const { user } = useStore((state) => ({ user: state.user }));
  const [data, setData] = useState<FeatureFlagStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!user) {
      setIsLoading(false);
      return;
    }

    let isCancelled = false;

    const fetchFeatureFlag = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const result = await checkFeatureFlag(featureFlagName);
        if (!isCancelled) {
          setData(result);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err instanceof Error ? err : new Error("Failed to check feature flag"));
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchFeatureFlag();

    return () => {
      isCancelled = true;
    };
  }, [featureFlagName, user]);

  return { data, isLoading, error };
}

export function useTeamFeatureFlags() {
  const { user } = useStore((state) => ({ user: state.user }));
  const [data, setData] = useState<TeamFeatureFlagsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!user) {
      setIsLoading(false);
      return;
    }

    let isCancelled = false;

    const fetchFeatureFlags = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const result = await getTeamFeatureFlags();
        if (!isCancelled) {
          setData(result);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err instanceof Error ? err : new Error("Failed to fetch team feature flags"));
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchFeatureFlags();

    return () => {
      isCancelled = true;
    };
  }, [user]);

  return { data, isLoading, error };
}

// Helper hook to check if a feature is enabled (returns boolean directly)
export function useIsFeatureEnabled(featureFlagName: string): boolean | null {
  const { data } = useFeatureFlag(featureFlagName);
  return data?.enabled ?? null;
}

