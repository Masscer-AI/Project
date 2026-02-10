import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import '@mantine/core/styles.css';
import '@mantine/dates/styles.css';
import { MantineProvider, createTheme } from '@mantine/core';
import { useStore } from "./modules/store";

const theme = createTheme({
  primaryColor: 'violet',
});

import Root from "./routes/root/page.tsx";

import { chatLoader } from "./routes/chat/loader.ts";
import "./index.css";
import Signup from "./routes/signup/page.tsx";
import ChatView from "./routes/chat/page.tsx";
import Layout from "./routes/Layout.tsx";
import Login from "./routes/login/page.tsx";

import Whatsapp from "./routes/whatsapp/page.tsx";

import { whatsappLoader } from "./routes/whatsapp/loader.ts";
import WorkflowsPage from "./routes/workflows/page.tsx";
import Share from "./routes/shares/page.tsx";
import { sharesLoader } from "./routes/shares/loader.ts";
import { ErrorPage } from "./routes/error/Page.tsx";
import { NotificationListener } from "./components/NotificationListener/NotificationListener.tsx";
import DashboardPage from "./routes/dashboard/page.tsx";
import AlertsPage from "./routes/dashboard/AlertsPage.tsx";
import AlertRulesPage from "./routes/dashboard/AlertRulesPage.tsx";
import TagsPage from "./routes/dashboard/TagsPage.tsx";
import OrganizationPage from "./routes/organization/page.tsx";
import KnowledgeBasePage from "./routes/knowledge-base/page.tsx";
import GenerationToolsPage from "./routes/generation-tools/page.tsx";
import ChatWidgetsPage from "./routes/chat-widgets/page.tsx";
import { ProtectedRoute } from "./components/ProtectedRoute/ProtectedRoute.tsx";
import SettingsPage from "./routes/settings/page.tsx";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    errorElement: <ErrorPage />,
    children: [
      {
        path: "/",
        element: <Root />,
        // loader: rootLoader,
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
        path: "/chat",
        element: (
          <>
            <ChatView />
            <NotificationListener />
          </>
        ),
        loader: chatLoader,
      },
      {
        path: "/whatsapp",
        element: <Whatsapp />,
        loader: whatsappLoader,
      },
      {
        path: "/workflows",
        element: <WorkflowsPage />,
      },
      {
        path: "/s",
        element: <Share />,
        loader: sharesLoader,
      },
      {
        path: "/dashboard",
        element: <DashboardPage />,
      },
      {
        path: "/dashboard/alerts",
        element: <AlertsPage />,
      },
      {
        path: "/dashboard/alert-rules",
        element: <AlertRulesPage />,
      },
      {
        path: "/dashboard/tags",
        element: <TagsPage />,
      },
      {
        path: "/organization",
        element: <OrganizationPage />,
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
        element: <SettingsPage />,
      },
    ],
  },
]);



function App() {
  const userTheme = useStore((s) => s.userPreferences.theme);
  const [systemDark, setSystemDark] = useState(
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );

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

  return (
    <MantineProvider theme={theme} forceColorScheme={colorScheme}>
      <RouterProvider router={router} />
    </MantineProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
