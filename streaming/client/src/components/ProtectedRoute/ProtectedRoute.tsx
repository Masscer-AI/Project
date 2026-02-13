import React, { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useStore } from "../../modules/store";
import { getUser } from "../../modules/apiCalls";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { TUserData } from "../../types/chatTypes";
import { Loader, Stack } from "@mantine/core";

interface ProtectedRouteProps {
  children: React.ReactNode;
  featureFlag: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, featureFlag }) => {
  const { user, setUser } = useStore((s) => ({ user: s.user, setUser: s.setUser }));
  const [authFailed, setAuthFailed] = useState(false);

  // On hard reload the store has no user yet — fetch it so the feature-flag
  // hook (which depends on `user`) can proceed.
  useEffect(() => {
    if (user || authFailed) return;
    getUser()
      .then((u) => setUser(u as TUserData))
      .catch(() => setAuthFailed(true));
  }, [user, authFailed, setUser]);

  const isEnabled = useIsFeatureEnabled(featureFlag);

  if (authFailed) {
    return <Navigate to="/login" replace />;
  }

  if (isEnabled === null) {
    return (
      <Stack align="center" justify="center" style={{ height: "100vh" }}>
        <Loader color="violet" />
      </Stack>
    );
  }

  if (!isEnabled) {
    return <Navigate to="/chat" replace />;
  }

  return <>{children}</>;
};