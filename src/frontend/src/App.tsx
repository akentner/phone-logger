import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from './components/Layout'
import { PbxPage } from './pages/PbxPage'
import { CallsPage } from './pages/CallsPage'
import { ContactsPage } from './pages/ContactsPage'
import { CachePage } from './pages/CachePage'
import { ConfigPage } from './pages/ConfigPage'

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

export function App() {
  return (
    <QueryClientProvider client={qc}>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/pbx" replace />} />
            <Route path="/pbx" element={<PbxPage />} />
            <Route path="/calls" element={<CallsPage />} />
            <Route path="/contacts" element={<ContactsPage />} />
            <Route path="/cache" element={<CachePage />} />
            <Route path="/config" element={<ConfigPage />} />
          </Route>
        </Routes>
      </HashRouter>
    </QueryClientProvider>
  )
}
