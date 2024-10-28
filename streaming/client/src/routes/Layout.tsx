import React from "react";
import { Outlet } from "react-router-dom";

import { Toaster } from "react-hot-toast";

const Layout: React.FC = () => {
  return (
    <div>
      <Toaster />
      <Outlet />
    </div>
  );
};

export default Layout;
