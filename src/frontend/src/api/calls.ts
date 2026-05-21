import { useQuery, useInfiniteQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { CallListResponse, CallLogResponse } from './types'

export interface CallsFilter {
  direction?: string
  status?: string
  line_id?: string
  search?: string
  msn?: string[]
}

function buildParams(filter: CallsFilter & { cursor?: string; limit?: number }): string {
  const p = new URLSearchParams()
  if (filter.cursor) p.set('cursor', filter.cursor)
  if (filter.limit) p.set('limit', String(filter.limit))
  if (filter.direction) p.set('direction', filter.direction)
  if (filter.status) p.set('status', filter.status)
  if (filter.line_id) p.set('line_id', filter.line_id)
  if (filter.search) p.set('search', filter.search)
  filter.msn?.forEach((m) => p.append('msn', m))
  return p.toString() ? `?${p}` : ''
}

export function useCallHistory(filter: CallsFilter = {}) {
  return useInfiniteQuery({
    queryKey: ['calls', 'history', filter],
    queryFn: ({ pageParam }) =>
      apiFetch<CallListResponse>(`/api/calls/history${buildParams({ ...filter, cursor: pageParam as string | undefined })}`),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
}

export function useCallEvents(filter: { search?: string } = {}) {
  return useInfiniteQuery({
    queryKey: ['calls', 'events', filter],
    queryFn: ({ pageParam }) =>
      apiFetch<CallLogResponse>(`/api/calls/events${buildParams({ ...filter, cursor: pageParam as string | undefined })}`),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
}

export function useRecentCalls(filter: CallsFilter = {}) {
  return useQuery({
    queryKey: ['calls', 'recent', filter],
    queryFn: () => apiFetch<CallListResponse>(`/api/calls/history${buildParams({ ...filter, limit: 50 })}`),
    refetchInterval: 10_000,
  })
}
