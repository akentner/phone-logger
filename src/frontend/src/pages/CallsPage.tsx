import { useState } from 'react'
import { useCallHistory, useCallEvents, type CallsFilter } from '../api/calls'
import { Badge } from '../components/Badge'
import { Search, ChevronDown } from 'lucide-react'
import type { CallStatus } from '../api/types'

const statusVariant: Record<CallStatus, 'default' | 'success' | 'warning' | 'danger' | 'info'> = {
  ringing: 'warning',
  dialing: 'info',
  answered: 'success',
  missed: 'danger',
  notReached: 'danger',
}

const statusLabel: Record<CallStatus, string> = {
  ringing: 'Klingelt',
  dialing: 'Wählt',
  answered: 'Beantwortet',
  missed: 'Verpasst',
  notReached: 'N. erreicht',
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatTs(ts: string | null): string {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })
}

type Tab = 'history' | 'events'

export function CallsPage() {
  const [tab, setTab] = useState<Tab>('history')
  const [search, setSearch] = useState('')
  const [direction, setDirection] = useState('')
  const [status, setStatus] = useState('')

  const filter: CallsFilter = {
    search: search || undefined,
    direction: direction || undefined,
    status: status || undefined,
  }

  const history = useCallHistory(filter)
  const events = useCallEvents({ search: search || undefined })

  const historyItems = history.data?.pages.flatMap((p) => p.items) ?? []
  const eventItems = events.data?.pages.flatMap((p) => p.items) ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold text-white">Anrufe</h1>
        <div className="flex gap-2 flex-wrap">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ha-muted" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Suche…"
              className="bg-ha-surface border border-ha-border rounded px-3 py-1.5 pl-8 text-sm text-white placeholder-ha-muted focus:outline-none focus:border-ha-accent w-44"
            />
          </div>
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            className="bg-ha-surface border border-ha-border rounded px-2 py-1.5 text-sm text-ha-muted focus:outline-none"
          >
            <option value="">Richtung</option>
            <option value="inbound">Eingehend</option>
            <option value="outbound">Ausgehend</option>
          </select>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="bg-ha-surface border border-ha-border rounded px-2 py-1.5 text-sm text-ha-muted focus:outline-none"
          >
            <option value="">Status</option>
            <option value="answered">Beantwortet</option>
            <option value="missed">Verpasst</option>
            <option value="notReached">N. erreicht</option>
          </select>
        </div>
      </div>

      <div className="flex gap-1 border-b border-ha-border">
        {(['history', 'events'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm transition-colors -mb-px border-b-2 ${
              tab === t ? 'border-ha-accent text-white' : 'border-transparent text-ha-muted hover:text-ha-text'
            }`}
          >
            {t === 'history' ? 'Anrufe' : 'Rohdaten'}
          </button>
        ))}
      </div>

      {tab === 'history' && (
        <div className="bg-ha-surface border border-ha-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ha-border text-ha-muted">
                <th className="text-left px-4 py-2">Zeit</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Von</th>
                <th className="text-left px-4 py-2">An</th>
                <th className="text-left px-4 py-2">Dauer</th>
                <th className="text-left px-4 py-2">Trunk</th>
              </tr>
            </thead>
            <tbody>
              {historyItems.map((call) => (
                <tr key={call.id} className="border-b border-ha-border last:border-0 hover:bg-ha-border/20">
                  <td className="px-4 py-2 text-ha-muted whitespace-nowrap">{formatTs(call.started_at)}</td>
                  <td className="px-4 py-2">
                    <Badge variant={statusVariant[call.status]}>{statusLabel[call.status]}</Badge>
                  </td>
                  <td className="px-4 py-2 text-white">{call.caller_display ?? call.caller_number}</td>
                  <td className="px-4 py-2 text-white">{call.called_display ?? call.called_number}</td>
                  <td className="px-4 py-2 text-ha-muted">{formatDuration(call.duration_seconds)}</td>
                  <td className="px-4 py-2 text-ha-muted">{call.trunk_id ?? '—'}</td>
                </tr>
              ))}
              {historyItems.length === 0 && !history.isLoading && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-ha-muted">Keine Anrufe</td></tr>
              )}
            </tbody>
          </table>
          {history.hasNextPage && (
            <div className="px-4 py-3 border-t border-ha-border">
              <button
                onClick={() => history.fetchNextPage()}
                disabled={history.isFetchingNextPage}
                className="flex items-center gap-1 text-sm text-ha-accent hover:underline disabled:opacity-50"
              >
                <ChevronDown size={14} />
                {history.isFetchingNextPage ? 'Lade…' : 'Mehr laden'}
              </button>
            </div>
          )}
        </div>
      )}

      {tab === 'events' && (
        <div className="bg-ha-surface border border-ha-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ha-border text-ha-muted">
                <th className="text-left px-4 py-2">Zeit</th>
                <th className="text-left px-4 py-2">Typ</th>
                <th className="text-left px-4 py-2">Richtung</th>
                <th className="text-left px-4 py-2">Nummer</th>
                <th className="text-left px-4 py-2">Quelle</th>
              </tr>
            </thead>
            <tbody>
              {eventItems.map((ev) => (
                <tr key={ev.id} className="border-b border-ha-border last:border-0 hover:bg-ha-border/20">
                  <td className="px-4 py-2 text-ha-muted whitespace-nowrap">{formatTs(ev.timestamp)}</td>
                  <td className="px-4 py-2"><Badge>{ev.event_type}</Badge></td>
                  <td className="px-4 py-2 text-ha-muted">{ev.direction}</td>
                  <td className="px-4 py-2 text-white">{ev.number}</td>
                  <td className="px-4 py-2 text-ha-muted">{ev.source}</td>
                </tr>
              ))}
              {eventItems.length === 0 && !events.isLoading && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-ha-muted">Keine Ereignisse</td></tr>
              )}
            </tbody>
          </table>
          {events.hasNextPage && (
            <div className="px-4 py-3 border-t border-ha-border">
              <button
                onClick={() => events.fetchNextPage()}
                disabled={events.isFetchingNextPage}
                className="flex items-center gap-1 text-sm text-ha-accent hover:underline disabled:opacity-50"
              >
                <ChevronDown size={14} />
                {events.isFetchingNextPage ? 'Lade…' : 'Mehr laden'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
