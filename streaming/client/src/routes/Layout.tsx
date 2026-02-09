import React from "react";
import { Outlet } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import i18n from "../i18next";
import { Toaster } from "react-hot-toast";
import { Themer } from "../components/Themer/Themer";

const Layout: React.FC = () => {
  return (
    <I18nextProvider i18n={i18n}>
      <Toaster />
      <Themer />
      <Outlet />
    </I18nextProvider>
  );
};

export default Layout;
