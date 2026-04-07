'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export function useHealthStatus() {
  const { data, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/health').then(r => r.data.data),
    refetchInterval: 30_000,
    staleTime: 25_000,
  });

  const overall = data?.overall ?? 'unknown';
  return { status: overall as 'healthy' | 'degraded' | 'down' | 'unknown', isLoading };
}
