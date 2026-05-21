import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { AppConfig, ResolveResult } from './types'

export function useAppConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: () => apiFetch<AppConfig>('/api/config'),
    staleTime: Infinity,
  })
}

export async function resolveNumber(number: string): Promise<ResolveResult> {
  return apiFetch<ResolveResult>(`/api/resolve/${encodeURIComponent(number)}`)
}
