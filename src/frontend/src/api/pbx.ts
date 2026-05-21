import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { PbxStatus } from './types'

export function usePbxStatus(autoRefresh = true) {
  return useQuery({
    queryKey: ['pbx', 'status'],
    queryFn: () => apiFetch<PbxStatus>('/api/pbx/status'),
    refetchInterval: autoRefresh ? 2_000 : false,
  })
}
