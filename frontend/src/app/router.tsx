import { createBrowserRouter, Navigate } from "react-router";
import { AnalysisWorkspace } from "@/features/workspace/AnalysisWorkspace";
import { ErrorPage } from "@/components/ErrorBoundary";
import React from "react";

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/workspace" replace />, errorElement: <ErrorPage /> },
  { path: "/workspace", element: <AnalysisWorkspace />, errorElement: <ErrorPage /> },
  { path: "*", element: <Navigate to="/workspace" replace />, errorElement: <ErrorPage /> },
]);
