import { useState } from 'react'
import { useAppConfig, resolveNumber } from '../api/config'
import { Badge } from '../components/Badge'
import { Search } from 'lucide-react'
import type { ResolveResult } from '../api/types'

function AdapterTable({ title, adapters }: { title: string; adapters: { type: string; name: string; enabled: boolean; order: number; config: Record<string, unknown> }[] }) {
  return (
    <section>
      <h2 className="text-sm font-medium text-ha-muted mb-2">{title}</h2>
      <div className="bg-ha-surface border border-ha-border rounded-lg divide-y divide-ha-border">
        {adapters.map((a) => (
          <div key={a.name} className="px-4 py-3">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="text-white text-sm font-medium">{a.name}</span>
                <Badge>{a.type}</Badge>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-ha-muted">#{a.order}</span>
                <Badge variant={a.enabled ? 'success' : 'default'}>{a.enabled ? 'Aktiv' : 'Inaktiv'}</Badge>
              </div>
            </div>
            {Object.keys(a.config).length > 0 && (
              <pre className="text-xs text-ha-muted bg-ha-bg rounded p-2 mt-1 overflow-x-auto">
                {JSON.stringify(a.config, null, 2)}
              </pre>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

export function ConfigPage() {
  const { data, isLoading } = useAppConfig()
  const [number, setNumber] = useState('')
  const [result, setResult] = useState<ResolveResult | null>(null)
  const [resolving, setResolving] = useState(false)
  const [error, setError] = useState('')

  async function handleResolve(e: React.FormEvent) {
    e.preventDefault()
    if (!number.trim()) return
    setResolving(true)
    setError('')
    setResult(null)
    try {
      setResult(await resolveNumber(number.trim()))
    } catch (err) {
      setError(String(err))
    } finally {
      setResolving(false)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-white">Konfiguration</h1>

      {/* Resolver test */}
      <section>
        <h2 className="text-sm font-medium text-ha-muted mb-2">Nummer auflösen</h2>
        <form onSubmit={handleResolve} className="flex gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ha-muted" />
            <input
              value={number}
              onChange={(e) => setNumber(e.target.value)}
              placeholder="+49..."
              className="bg-ha-surface border border-ha-border rounded px-3 py-1.5 pl-8 text-sm text-white placeholder-ha-muted focus:outline-none focus:border-ha-accent w-64"
            />
          </div>
          <button type="submit" disabled={resolving} className="bg-ha-accent hover:bg-blue-600 text-white rounded px-4 py-1.5 text-sm transition-colors disabled:opacity-50">
            {resolving ? 'Löse auf…' : 'Auflösen'}
          </button>
        </form>
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
        {result && (
          <pre className="mt-2 text-xs bg-ha-surface border border-ha-border rounded p-3 text-ha-text overflow-x-auto">
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </section>

      {isLoading ? (
        <p className="text-ha-muted">Lade…</p>
      ) : data ? (
        <>
          <AdapterTable title="Eingabe-Adapter" adapters={data.input_adapters} />
          <AdapterTable title="Resolver-Adapter" adapters={data.resolver_adapters} />
          <AdapterTable title="Ausgabe-Adapter" adapters={data.output_adapters} />
        </>
      ) : null}
    </div>
  )
}
