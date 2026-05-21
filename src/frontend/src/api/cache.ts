import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { CacheResponse } from './types'

export function useCache() {
  return useQuery({
    queryKey: ['cache'],
    queryFn: () => apiFetch<CacheResponse>('/api/cache'),
  })
}

export function useDeleteCacheEntry() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (number: string) =>
      apiFetch<void>(`/api/cache/${encodeURIComponent(number)}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cache'] }),
  })
}

export function useCleanupCache() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<{ status: string; removed: number }>('/api/cache/cleanup', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cache'] }),
  })
}
