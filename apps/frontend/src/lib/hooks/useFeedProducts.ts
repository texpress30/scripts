"use client";

import { useQuery } from "@tanstack/react-query";
import type { ProductsListResponse, ProductStats } from "@/lib/types/feed-management";
import { apiRequest, ApiRequestError } from "@/lib/api";
import { mockProducts, mockProductStats, mockProductCategories } from "@/lib/mocks/feedProducts";

const PRODUCTS_KEY = (sourceId: number) => ["feed-products", sourceId] as const;
const STATS_KEY = (sourceId: number) => ["feed-product-stats", sourceId] as const;
const CATEGORIES_KEY = (sourceId: number) => ["feed-product-categories", sourceId] as const;

type ProductsQueryParams = {
  page: number;
  limit: number;
  search: string;
  category: string;
};

async function fetchProducts(sourceId: number, params: ProductsQueryParams): Promise<ProductsListResponse> {
  const skip = (params.page - 1) * params.limit;
  const qs = new URLSearchParams({
    skip: String(skip),
    limit: String(params.limit),
    ...(params.search ? { search: params.search } : {}),
    ...(params.category ? { category: params.category } : {}),
  });
  try {
    return await apiRequest<ProductsListResponse>(
      `/subaccount/1/feed-sources/${sourceId}/products?${qs.toString()}`,
      { cache: "no-store" },
    );
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(300);
      let items = [...mockProducts];
      if (params.search) {
        const q = params.search.toLowerCase();
        items = items.filter((p) => p.title.toLowerCase().includes(q) || p.description.toLowerCase().includes(q));
      }
      if (params.category) {
        items = items.filter((p) => p.category === params.category);
      }
      const total = items.length;
      items = items.slice(skip, skip + params.limit);
      return { items, total, skip, limit: params.limit };
    }
    throw err;
  }
}

async function fetchStats(sourceId: number): Promise<ProductStats> {
  try {
    return await apiRequest<ProductStats>(
      `/subaccount/1/feed-sources/${sourceId}/products/stats`,
      { cache: "no-store" },
    );
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(200);
      return mockProductStats;
    }
    throw err;
  }
}

async function fetchCategories(sourceId: number): Promise<string[]> {
  try {
    const res = await apiRequest<{ categories: string[] }>(
      `/subaccount/1/feed-sources/${sourceId}/products/categories`,
      { cache: "no-store" },
    );
    return res.categories;
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      await delay(200);
      return mockProductCategories;
    }
    throw err;
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useFeedProducts(sourceId: number, params: ProductsQueryParams) {
  const { data, isLoading, error } = useQuery<ProductsListResponse>({
    queryKey: [...PRODUCTS_KEY(sourceId), params.page, params.limit, params.search, params.category],
    queryFn: () => fetchProducts(sourceId, params),
    enabled: sourceId > 0,
  });

  return {
    products: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading,
    error: error instanceof Error ? error.message : null,
  };
}

export function useFeedProductStats(sourceId: number) {
  const { data, isLoading, error } = useQuery<ProductStats>({
    queryKey: STATS_KEY(sourceId),
    queryFn: () => fetchStats(sourceId),
    enabled: sourceId > 0,
  });

  return {
    stats: data ?? null,
    isLoading,
    error: error instanceof Error ? error.message : null,
  };
}

export function useFeedProductCategories(sourceId: number) {
  const { data, isLoading } = useQuery<string[]>({
    queryKey: CATEGORIES_KEY(sourceId),
    queryFn: () => fetchCategories(sourceId),
    enabled: sourceId > 0,
  });

  return {
    categories: data ?? [],
    isLoading,
  };
}
