import { appBasePath } from "./utils/basePath";
import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./style.css";
import "./appearance.css";
import "./ios-web.css";
const client = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnReconnect: true },
    mutations: { retry: false, networkMode: "always" },
  },
});
const router = createBrowserRouter([{ path: "*", element: <App /> }], { basename: appBasePath() });
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
