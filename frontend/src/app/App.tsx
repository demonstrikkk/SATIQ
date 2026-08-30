import React from "react";
import { RouterProvider } from "react-router";
import { router } from "./router";
import { Providers } from "./providers";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Bootstrap } from "./Bootstrap";


export default function App() {
  return (
    <ErrorBoundary>
      <Bootstrap>
        <Providers>
          <RouterProvider router={router} />
        </Providers>
      </Bootstrap>
    </ErrorBoundary>
  );
}
