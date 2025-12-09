import React from "react";
import { Navigate } from "react-router-dom";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";

interface ProtectedRouteProps {
  children: React.ReactNode;
  featureFlag: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, featureFlag }) => {
  const isEnabled = useIsFeatureEnabled(featureFlag);

  if (isEnabled === null) {
    // Still loading
    return <div>Loading...</div>;
  }

  if (!isEnabled) {
    // Feature flag disabled, redirect to chat
    return <Navigate to="/chat" replace />;
  }

  return <>{children}</>;
};