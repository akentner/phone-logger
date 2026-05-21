import { useCache, useDeleteCacheEntry, useCleanupCache } from '../api/cache'
import { Badge } from '../components/Badge'
import { Trash2 } from 'lucide-react'

function formatTs(ts: string): string {
  return new Date(ts).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })
}

export function CachePage() {
  const { data, isLoading } = useCache()
  const deleteMut = useDeleteCacheEntry()
  const cleanupMut = useCleanupCache()

  const entries = data?.entries ?? []
  const expiredCount = entries.filter((e) => e.expired).length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-white">Cache</h1>
          <p className="text-sm text-ha-muted">{entries.length} Einträge, {expiredCount} abgelaufen</p>
        </div>
        {expiredCount > 0 && (
          <button
            onClick={() => cleanupMut.mutate()}
            disabled={cleanupMut.isPending}
            className="flex items-center gap-1.5 bg-red-800 hover:bg-red-700 text-white rounded px-3 py-1.5 text-sm transition-colors disabled:opacity-50"
          >
            <Trash2 size={14} />
            {cleanupMut.isPending ? 'Bereinige…' : `${expiredCount} abgelaufene löschen`}
          </button>
        )}
      </div>

      {isLoading ? (
        <p className="text-ha-muted">Lade…</p>
      ) : (
        <div className="bg-ha-surface border border-ha-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ha-border text-ha-muted">
                <th className="text-left px-4 py-2">Nummer</th>
                <th className="text-left px-4 py-2">Name</th>
                <th className="text-left px-4 py-2">Adapter</th>
                <th className="text-left px-4 py-2">Spam</th>
                <th className="text-left px-4 py-2">Gecacht</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.number} className="border-b border-ha-border last:border-0 hover:bg-ha-border/20">
                  <td className="px-4 py-2 text-ha-muted font-mono">{entry.number}</td>
                  <td className="px-4 py-2 text-white">{entry.result_name ?? '—'}</td>
                  <td className="px-4 py-2"><Badge>{entry.adapter}</Badge></td>
                  <td className="px-4 py-2">
                    {entry.spam_score != null && entry.spam_score > 0 && (
                      <Badge variant={entry.spam_score >= 7 ? 'danger' : 'warning'}>{entry.spam_score}</Badge>
                    )}
                  </td>
                  <td className="px-4 py-2 text-ha-muted">{formatTs(entry.cached_at)}</td>
                  <td className="px-4 py-2">
                    <Badge variant={entry.expired ? 'danger' : 'success'}>
                      {entry.expired ? 'Abgelaufen' : 'Gültig'}
                    </Badge>
                  </td>
                  <td className="px-4 py-2">
                    <button
                      onClick={() => deleteMut.mutate(entry.number)}
                      className="text-ha-muted hover:text-red-400 transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-ha-muted">Cache leer</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
