import { NavLink, Outlet } from 'react-router-dom'
import { Phone, Activity, Users, Database, Settings } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import clsx from 'clsx'

const nav = [
  { to: '/pbx', icon: Activity, label: 'PBX' },
  { to: '/calls', icon: Phone, label: 'Anrufe' },
  { to: '/contacts', icon: Users, label: 'Kontakte' },
  { to: '/cache', icon: Database, label: 'Cache' },
  { to: '/config', icon: Settings, label: 'Config' },
]

export function Layout() {
  const { data: openapi } = useQuery({
    queryKey: ['openapi'],
    queryFn: () => apiFetch<{ info: { version: string } }>('/openapi.json'),
    staleTime: Infinity,
  })
  const version = openapi?.info?.version

  return (
    <div className="min-h-screen flex flex-col bg-ha-bg text-ha-text">
      <header className="sticky top-0 z-50 bg-ha-surface border-b border-ha-border">
        <div className="max-w-7xl mx-auto px-4 flex items-center gap-6 h-14">
          <span className="font-semibold text-white flex items-center gap-2">
            <Phone size={18} className="text-ha-accent" />
            Phone Logger
          </span>
          <nav className="flex gap-1">
            {nav.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors',
                    isActive
                      ? 'bg-ha-accent text-white'
                      : 'text-ha-muted hover:text-ha-text hover:bg-ha-border',
                  )
                }
              >
                <Icon size={15} />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-ha-border text-ha-muted text-xs text-center py-3">
        Phone Logger{version && <> · v{version}</>}
      </footer>
    </div>
  )
}
