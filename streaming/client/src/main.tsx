import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";

import Root from "./routes/root/page.tsx";
import { rootLoader } from "./routes/root/loader.ts";
import { chatLoader } from "./routes/chat/loader.ts";
import "./index.css";
import Signup from "./routes/signup/page.tsx";
import ChatView from "./routes/chat/page.tsx";
import Layout from "./routes/Layout.tsx";
import Login from "./routes/login/page.tsx";
import Tools from "./routes/tools/page.tsx";
import Whatsapp from "./routes/whatsapp/page.tsx";
import { whatsappLoader } from "./routes/whatsapp/loader.ts";
const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    // element: <Root />,
    children: [
      {
        path: "/",
        element: <Root />,
        loader: rootLoader,
      },
    ],
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
    element: <ChatView />,
    loader: chatLoader,
    // children: [
    //   {
    //     path: "c/:conversationId",
    //     element: <ChatView />,
    //     loader: chatLoader,
    //   },
    // ],
  },
  {
    path: "/tools",
    element: <Tools />,
  },
  {
    path: "/whatsapp",
    element: <Whatsapp />,
    loader: whatsappLoader,
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
