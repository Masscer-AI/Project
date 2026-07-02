import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import '@mantine/core/styles.css';
import '@mantine/dates/styles.css';
import { MantineProvider } from '@mantine/core';
import { GoogleOAuthProvider } from "@react-oauth/google";
import { useStore } from "./modules/store";
import { hasGoogleOAuthClientId, VITE_GOOGLE_CLIENT_ID } from "./modules/googleEnv";
import { getTenantConfig } from "./modules/apiCalls";
import {
  applyTenantDocumentBranding,
  buildMantineTheme,
} from "./utils/tenantTheme";

import Root from "./routes/root/page.tsx";

import { chatLoader } from "./routes/chat/loader.ts";
import "./index.css";
import Signup from "./routes/signup/page.tsx";
import ChatView from "./routes/chat/page.tsx";
import Layout from "./routes/Layout.tsx";
import Login from "./routes/login/page.tsx";
import ForgotPassword from "./routes/forgot-password/page.tsx";
import ResetPassword from "./routes/reset-password/page.tsx";
import AuthCallback from "./routes/auth/callback/page.tsx";
import AuthGoogleBridge from "./routes/auth/google/page.tsx";

import Whatsapp from "./routes/whatsapp/page.tsx";
import WorkflowsPage from "./routes/workflows/page.tsx";
import Share from "./routes/shares/page.tsx";
import { sharesLoader } from "./routes/shares/loader.ts";
import { ErrorPage } from "./routes/error/Page.tsx";
import { NotificationListener } from "./components/NotificationListener/NotificationListener.tsx";
import { AgentTaskListener } from "./components/AgentTaskListener/AgentTaskListener.tsx";
import { ConversationTakeoverListener } from "./components/ConversationTakeoverListener/ConversationTakeoverListener.tsx";
import DashboardPage from "./routes/dashboard/page.tsx";
import AlertsHubPage from "./routes/dashboard/AlertsHubPage.tsx";
import TagsPage from "./routes/dashboard/TagsPage.tsx";
import OrganizationPage from "./routes/organization/page.tsx";
import KnowledgeBasePage from "./routes/knowledge-base/page.tsx";
import GenerationToolsPage from "./routes/generation-tools/page.tsx";
import ChatWidgetsPage from "./routes/chat-widgets/page.tsx";
import { ProtectedRoute } from "./components/ProtectedRoute/ProtectedRoute.tsx";
import SettingsPage from "./routes/settings/page.tsx";
import IntegrationsPage from "./routes/settings/integrations/page.tsx";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    errorElement: <ErrorPage />,
    children: [
      {
        path: "/",
        element: <Root />,
      },
      {
        path: "/signup",
        element: <Signup />,
      },
      {
        path: "/login",
        element: <Login />,
      },
      {
        path: "/forgot-password",
        element: <ForgotPassword />,
      },
      {
        path: "/reset-password",
        element: <ResetPassword />,
      },
      {
        path: "/auth/callback",
        element: <AuthCallback />,
      },
      {
        path: "/auth/google",
        element: <AuthGoogleBridge />,
      },
      {
        path: "/chat",
        element: (
          <>
            <ChatView />
            <NotificationListener />
            <AgentTaskListener />
            <ConversationTakeoverListener />
          </>
        ),
        loader: chatLoader,
      },
      {
        path: "/whatsapp",
        element: (
          <ProtectedRoute featureFlag="whatsapp-numbers-management">
            <Whatsapp />
          </ProtectedRoute>
        ),
      },
      {
        path: "/workflows",
        element: (
          <ProtectedRoute>
            <WorkflowsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "/s",
        element: <Share />,
        loader: sharesLoader,
      },
      {
        path: "/dashboard",
        element: (
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "/dashboard/alerts",
        element: (
          <ProtectedRoute>
            <AlertsHubPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "/dashboard/tags",
        element: (
          <ProtectedRoute>
            <TagsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "/organization",
        element: (
          <ProtectedRoute>
            <OrganizationPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "/knowledge-base",
        element: (
          <ProtectedRoute featureFlag="train-agents">
            <KnowledgeBasePage />
          </ProtectedRoute>
        ),
      },
      {
        path: "/generation-tools",
        element: (
          <ProtectedRoute featureFlag="audio-tools">
            <GenerationToolsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "/chat-widgets",
        element: (
          <ProtectedRoute featureFlag="chat-widgets-management">
            <ChatWidgetsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "/settings",
        element: (
          <ProtectedRoute featureFlag="can-edit-preferences">
            <SettingsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "/settings/integrations",
        element: (
          <ProtectedRoute featureFlag="can-connect-drive-account">
            <IntegrationsPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
]);

function App() {
  const { userTheme, tenantBranding, setTenantBranding } = useStore((s) => ({
    userTheme: s.userPreferences.theme,
    tenantBranding: s.tenantBranding,
    setTenantBranding: s.setTenantBranding,
  }));
  const [systemDark, setSystemDark] = useState(
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );

  useEffect(() => {
    getTenantConfig()
      .then((config) => {
        const hasBranding = Boolean(
          config.app_name ||
            config.logo_url ||
            config.favicon_url ||
            config.theme?.primary_color ||
            config.hide_powered_by
        );
        const branding = hasBranding ? config : null;
        setTenantBranding(branding);
        applyTenantDocumentBranding(config);
      })
      .catch(() => {
        setTenantBranding(null);
      });
  }, [setTenantBranding]);

  useEffect(() => {
    applyTenantDocumentBranding(tenantBranding ?? undefined);
  }, [tenantBranding]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const colorScheme: "light" | "dark" =
    userTheme === "system"
      ? systemDark
        ? "dark"
        : "light"
      : (userTheme as "light" | "dark") || "dark";

  const theme = useMemo(
    () => buildMantineTheme(tenantBranding),
    [tenantBranding]
  );

  return (
    <MantineProvider theme={theme} forceColorScheme={colorScheme}>
      <RouterProvider router={router} />
    </MantineProvider>
  );
}

const rootTree = hasGoogleOAuthClientId ? (
  <GoogleOAuthProvider clientId={VITE_GOOGLE_CLIENT_ID}>
    <App />
  </GoogleOAuthProvider>
) : (
  <App />
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>{rootTree}</React.StrictMode>
);
