import { GraphEdge } from '../../lib/api'

const EDGE_COLORS: Record<string, string> = {
  triggers: '#6366f1',
  mutates: '#0ea5e9',
  governs: '#10b981',
  conflicts_with: '#ef4444',
  supersedes: '#f59e0b',
  accessible_only_if: '#8b5cf6',
  parent_of: '#6b7280',
  sibling_of: '#9ca3af',
  enables: '#22c55e',
  blocks: '#f97316',
  references: '#6b7280',
}

interface Props {
  edges: GraphEdge[]
}

export function EdgeList({ edges }: Props) {
  if (!edges.length) return <div style={{ fontSize: 12, color: '#9ca3af' }}>No edges</div>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {edges.map((e) => {
        const color = EDGE_COLORS[e.edge_type] ?? '#9ca3af'
        return (
          <div
            key={e.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 12,
              padding: '6px 10px',
              background: '#f9fafb',
              borderRadius: 6,
              border: '1px solid #e5e7eb',
            }}
          >
            <span
              style={{
                fontSize: 10,
                padding: '1px 7px',
                borderRadius: 99,
                background: color + '18',
                color,
                border: `1px solid ${color}40`,
                whiteSpace: 'nowrap',
              }}
            >
              {e.edge_type}
            </span>
            <span style={{ fontFamily: 'monospace', color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              → {e.target_node_id.slice(0, 8)}…
            </span>
            {e.confidence != null && (
              <span style={{ color: '#9ca3af', marginLeft: 'auto', flexShrink: 0 }}>
                {Math.round(e.confidence)}%
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
