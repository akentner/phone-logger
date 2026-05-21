import { useState } from 'react'
import { usePbxStatus } from '../api/pbx'
import { Badge } from '../components/Badge'
import clsx from 'clsx'
import type { LineStatus } from '../api/types'

const statusVariant: Record<LineStatus, 'default' | 'success' | 'warning' | 'danger' | 'info'> = {
  idle: 'default',
  ring: 'warning',
  call: 'info',
  talking: 'success',
  finished: 'default',
  missed: 'danger',
  notReached: 'danger',
}

const statusLabel: Record<LineStatus, string> = {
  idle: 'Frei',
  ring: 'Klingelt',
  call: 'Wählt',
  talking: 'Gespräch',
  finished: 'Beendet',
  missed: 'Verpasst',
  notReached: 'N. erreicht',
}

export function PbxPage() {
  const [autoRefresh, setAutoRefresh] = useState(true)
  const { data, isLoading, dataUpdatedAt } = usePbxStatus(autoRefresh)

  if (isLoading) return <p className="text-ha-muted">Lade PBX-Status…</p>
  if (!data) return null

  const activeLines = data.lines.filter((l) => l.status !== 'idle')
  const updatedAt = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : '—'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">PBX-Status</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-ha-muted">Aktualisiert: {updatedAt}</span>
          <label className="flex items-center gap-2 text-sm text-ha-muted cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="accent-ha-accent"
            />
            Auto-Refresh (2s)
          </label>
        </div>
      </div>

      {/* Active lines highlight */}
      {activeLines.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {activeLines.map((line) => (
            <div key={line.line_id} className="bg-ha-surface border border-ha-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-white">Leitung {line.line_id}</span>
                <Badge variant={statusVariant[line.status]}>{statusLabel[line.status]}</Badge>
              </div>
              <div className="text-sm text-ha-muted space-y-0.5">
                {line.caller_display && <div>Von: <span className="text-white">{line.caller_display}</span></div>}
                {line.called_display && <div>An: <span className="text-white">{line.called_display}</span></div>}
                {line.trunk_id && <div>Trunk: {line.trunk_id}</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Lines table */}
      <section>
        <h2 className="text-sm font-medium text-ha-muted mb-2">Leitungen</h2>
        <div className="bg-ha-surface border border-ha-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ha-border text-ha-muted">
                <th className="text-left px-4 py-2">Leitung</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Von</th>
                <th className="text-left px-4 py-2">An</th>
                <th className="text-left px-4 py-2">Trunk</th>
              </tr>
            </thead>
            <tbody>
              {data.lines.map((line) => (
                <tr key={line.line_id} className={clsx('border-b border-ha-border last:border-0', line.status !== 'idle' && 'bg-ha-border/20')}>
                  <td className="px-4 py-2 text-white">{line.line_id}</td>
                  <td className="px-4 py-2"><Badge variant={statusVariant[line.status]}>{statusLabel[line.status]}</Badge></td>
                  <td className="px-4 py-2 text-ha-muted">{line.caller_display ?? '—'}</td>
                  <td className="px-4 py-2 text-ha-muted">{line.called_display ?? '—'}</td>
                  <td className="px-4 py-2 text-ha-muted">{line.trunk_id ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid sm:grid-cols-3 gap-4">
        {/* Trunks */}
        <section>
          <h2 className="text-sm font-medium text-ha-muted mb-2">Trunks</h2>
          <div className="bg-ha-surface border border-ha-border rounded-lg divide-y divide-ha-border">
            {data.trunks.map((t) => (
              <div key={t.id} className="flex items-center justify-between px-4 py-2 text-sm">
                <div>
                  <div className="text-white">{t.label ?? t.id}</div>
                  <div className="text-ha-muted text-xs">{t.id} · {t.type.toUpperCase()}</div>
                </div>
                <Badge variant={t.busy ? 'warning' : 'success'}>{t.busy ? 'Besetzt' : 'Frei'}</Badge>
              </div>
            ))}
          </div>
        </section>

        {/* MSNs */}
        <section>
          <h2 className="text-sm font-medium text-ha-muted mb-2">MSNs</h2>
          <div className="bg-ha-surface border border-ha-border rounded-lg divide-y divide-ha-border">
            {data.msns.map((m) => (
              <div key={m.msn} className="px-4 py-2 text-sm">
                <div className="text-white">{m.label ?? m.msn}</div>
                <div className="text-ha-muted text-xs">{m.e164}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Devices */}
        <section>
          <h2 className="text-sm font-medium text-ha-muted mb-2">Geräte</h2>
          <div className="bg-ha-surface border border-ha-border rounded-lg divide-y divide-ha-border">
            {data.devices.map((d) => (
              <div key={d.id} className="flex items-center justify-between px-4 py-2 text-sm">
                <div>
                  <div className="text-white">{d.name}</div>
                  <div className="text-ha-muted text-xs">{d.extension}</div>
                </div>
                <Badge>{d.type}</Badge>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
