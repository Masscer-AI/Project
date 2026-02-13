import React, { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import i18n from "../i18next";
import { Toaster } from "react-hot-toast";
import { Themer } from "../components/Themer/Themer";
import { useStore } from "../modules/store";
import { getUser } from "../modules/apiCalls";
import { TUserData } from "../types/chatTypes";

const Layout: React.FC = () => {
  const { user, setUser } = useStore((s) => ({
    user: s.user,
    setUser: s.setUser,
  }));

  // Hydrate the user on first mount so every route (sidebar, feature flags,
  // etc.) has access to it — not just routes with their own loader.
  useEffect(() => {
    if (user) return;
    const token = localStorage.getItem("token");
    if (!token) return;
    getUser()
      .then((u) => setUser(u as TUserData))
      .catch(() => {
        /* not logged in — pages will redirect as needed */
      });
  }, [user, setUser]);

  return (
    <I18nextProvider i18n={i18n}>
      <Toaster />
      <Themer />
      <Outlet />
    </I18nextProvider>
  );
};

export default Layout;
