"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";

export type ColumnDef = {
  key: string;
  label: string;
  type: "string" | "url" | "image" | "price";
};

export type ChannelProductsResponse = {
  channel_id: string;
  products: Record<string, unknown>[];
  columns: ColumnDef[];
  total: number;
  page: number;
  per_page: number;
};

const PRODUCTS_KEY = (channelId: string, page: number, perPage: number, search: string) =>
  ["channel-products", channelId, page, perPage, search] as const;

export function useChannelProducts(
  channelId: string | null,
  page: number,
  perPage: number,
  search: string = "",
) {
  const { data, isLoading, error } = useQuery<ChannelProductsResponse>({
    queryKey: PRODUCTS_KEY(channelId ?? "", page, perPage, search),
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
      });
      if (search) params.set("search", search);
      return apiRequest<ChannelProductsResponse>(
        `/channels/${channelId}/products?${params.toString()}`,
        { cache: "no-store" },
      );
    },
    enabled: !!channelId,
    retry: 1,
  });

  return {
    products: data?.products ?? [],
    columns: data?.columns ?? [],
    total: data?.total ?? 0,
    page: data?.page ?? 1,
    perPage: data?.per_page ?? perPage,
    isLoading: channelId ? isLoading : false,
    error: error instanceof Error ? error.message : null,
  };
}
