"use client";

import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let client: QueryClient | null = null;

function getQueryClient(): QueryClient {
  if (!client) {
    client = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 10_000, // dữ liệu tươi 10s: chuyển tab không fetch lại vô ích
          gcTime: 5 * 60_000,
          retry: 1,
          refetchOnWindowFocus: false, // trang live đã có polling riêng
        },
        mutations: { retry: 0 },
      },
    });
  }
  return client;
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(getQueryClient);
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
