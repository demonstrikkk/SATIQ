import React from "react";
import { RouterProvider } from "react-router";
import { router } from "./router";
import { Providers } from "./providers";
import { ErrorBoundary } from "@/components/ErrorBoundary";


export default function App() {
  return (
    <ErrorBoundary>
      <Providers>
        <RouterProvider router={router} />
      </Providers>
    </ErrorBoundary>
  );
}
