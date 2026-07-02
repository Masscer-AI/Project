import React, { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useStore } from "../../modules/store";
import { getUser } from "../../modules/apiCalls";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { TUserData } from "../../types/chatTypes";
import { loginUrlWithNext } from "../../utils/loginRedirect";
import { Loader, Stack } from "@mantine/core";

interface ProtectedRouteProps {
  children: React.ReactNode;
  /** When omitted, only authentication is required (login redirect with ?next=). */
  featureFlag?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  featureFlag,
}) => {
  const { user, setUser } = useStore((s) => ({ user: s.user, setUser: s.setUser }));
  const location = useLocation();
  const [authFailed, setAuthFailed] = useState(false);

  // On hard reload the store has no user yet — fetch it so the feature-flag
  // hook (which depends on `user`) can proceed.
  useEffect(() => {
    if (user || authFailed) return;
    getUser()
      .then((u) => setUser(u as TUserData))
      .catch(() => setAuthFailed(true));
  }, [user, authFailed, setUser]);

  // Always call hooks; result is only used when featureFlag is set.
  const isEnabled = useIsFeatureEnabled(featureFlag ?? "__auth_only__");

  if (authFailed) {
    const returnPath = `${location.pathname}${location.search}`;
    return <Navigate to={loginUrlWithNext(returnPath)} replace />;
  }

  if (!featureFlag) {
    if (!user) {
      return (
        <Stack align="center" justify="center" style={{ height: "100vh" }}>
          <Loader color="violet" />
        </Stack>
      );
    }
    return <>{children}</>;
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