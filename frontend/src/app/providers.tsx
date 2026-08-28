import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
const qc = new QueryClient({ defaultOptions:{ queries:{ retry:1, refetchOnWindowFocus:false }}});
export function Providers({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={qc}>{children}<Toaster theme="dark" richColors /></QueryClientProvider>;
}
