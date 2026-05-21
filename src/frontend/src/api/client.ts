declare global {
  interface Window {
    __ingress_path?: string
  }
}

function getBase(): string {
  if (window.__ingress_path) return window.__ingress_path.replace(/\/$/, '')
  // detect ingress path from current URL when served via HA ingress
  const match = window.location.pathname.match(/^(\/api\/hassio_ingress\/[^/]+)/)
  return match ? match[1] : ''
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${getBase()}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}
