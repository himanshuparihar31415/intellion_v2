import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { GraphPage } from './routes/graph/GraphPage'
import { TrainingPage } from './routes/training/TrainingPage'
import { MissionsPage } from './routes/missions/MissionsPage'
import { ConflictsPage } from './routes/conflicts/ConflictsPage'
import { api } from '../lib/api'
import { useMutation } from '@tanstack/react-query'

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000 } } })

type Route = 'graph' | 'training' | 'missions' | 'conflicts'

const NAV: { id: Route; label: string }[] = [
  { id: 'training', label: 'Training' },
  { id: 'graph', label: 'Knowledge Graph' },
  { id: 'missions', label: 'Missions' },
  { id: 'conflicts', label: 'Conflicts' },
]

function Shell() {
  const [route, setRoute] = useState<Route>('training')
  const [intellionId, setIntellionId] = useState('')
  const [setupName, setSetupName] = useState('')
  const [setupUrl, setSetupUrl] = useState('')

  const create = useMutation({
    mutationFn: () => api.intellions.create(setupName, setupUrl),
    onSuccess: (data) => setIntellionId(data.id),
  })

  if (!intellionId) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f9fafb' }}>
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '32px 36px', width: 400, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#111827' }}>Intellion</div>
          <div style={{ fontSize: 13, color: '#6b7280' }}>Create an Intellion to start training.</div>
          <input
            placeholder="Name (e.g. My App)"
            value={setupName}
            onChange={(e) => setSetupName(e.target.value)}
            style={input}
          />
          <input
            placeholder="Target URL (e.g. https://myapp.com)"
            value={setupUrl}
            onChange={(e) => setSetupUrl(e.target.value)}
            style={input}
          />
          <div style={{ fontSize: 12, color: '#9ca3af' }}>or paste an existing ID:</div>
          <input
            placeholder="intellion-id"
            value={intellionId}
            onChange={(e) => setIntellionId(e.target.value)}
            style={input}
          />
          <button
            onClick={() => create.mutate()}
            disabled={create.isPending || !setupName || !setupUrl}
            style={{ background: '#6366f1', color: '#fff', border: 'none', borderRadius: 6, padding: '9px 16px', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}
          >
            {create.isPending ? 'Creating…' : 'Create Intellion'}
          </button>
        </div>
      </div>
    )
  }

  const pages: Record<Route, JSX.Element> = {
    graph: <GraphPage intellion_id={intellionId} />,
    training: <TrainingPage intellion_id={intellionId} />,
    missions: <MissionsPage intellion_id={intellionId} />,
    conflicts: <ConflictsPage intellion_id={intellionId} />,
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', fontFamily: 'system-ui, sans-serif' }}>
      {/* Sidebar */}
      <nav style={{ width: 200, background: '#111827', display: 'flex', flexDirection: 'column', padding: '20px 0', flexShrink: 0 }}>
        <div style={{ padding: '0 16px 20px', fontSize: 15, fontWeight: 700, color: '#fff' }}>
          Intellion
        </div>
        {NAV.map((n) => (
          <button
            key={n.id}
            onClick={() => setRoute(n.id)}
            style={{
              background: route === n.id ? '#1f2937' : 'transparent',
              border: 'none',
              color: route === n.id ? '#fff' : '#9ca3af',
              textAlign: 'left',
              padding: '9px 16px',
              fontSize: 13,
              cursor: 'pointer',
              fontWeight: route === n.id ? 500 : 400,
            }}
          >
            {n.label}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <div style={{ padding: '0 16px', fontSize: 10, color: '#4b5563', wordBreak: 'break-all' }}>
          {intellionId}
        </div>
      </nav>

      {/* Main */}
      <main style={{ flex: 1, overflowY: 'auto', padding: 24, background: '#f9fafb' }}>
        <div style={{ maxWidth: 1100 }}>
          <h2 style={{ margin: '0 0 20px', fontSize: 18, fontWeight: 600, color: '#111827' }}>
            {NAV.find((n) => n.id === route)?.label}
          </h2>
          {pages[route]}
        </div>
      </main>
    </div>
  )
}

const input: React.CSSProperties = {
  border: '1px solid #d1d5db',
  borderRadius: 6,
  padding: '7px 10px',
  fontSize: 13,
  color: '#111827',
  background: '#fff',
  width: '100%',
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <Shell />
    </QueryClientProvider>
  )
}
