import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { Contact, ContactCreate, ContactUpdate } from './types'

export function useContacts() {
  return useQuery({
    queryKey: ['contacts'],
    queryFn: () => apiFetch<Contact[]>('/api/contacts'),
  })
}

export function useCreateContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ContactCreate) =>
      apiFetch<Contact>('/api/contacts', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['contacts'] }),
  })
}

export function useUpdateContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ number, data }: { number: string; data: ContactUpdate }) =>
      apiFetch<Contact>(`/api/contacts/${encodeURIComponent(number)}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['contacts'] }),
  })
}

export function useDeleteContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (number: string) =>
      apiFetch<void>(`/api/contacts/${encodeURIComponent(number)}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['contacts'] }),
  })
}
