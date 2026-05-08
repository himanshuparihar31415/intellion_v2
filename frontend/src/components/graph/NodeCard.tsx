import { KnowledgeNode } from '../../lib/api'
import { ConfidenceBar } from './ConfidenceBar'

const LAYER_NAMES: Record<number, string> = {
  1: 'Structural',
  2: 'Interaction',
  3: 'Behavioral',
  4: 'Rule',
}

const LAYER_COLORS: Record<number, string> = {
  1: '#6366f1',
  2: '#0ea5e9',
  3: '#10b981',
  4: '#f59e0b',
}

const STATUS_COLORS: Record<string, string> = {
  active: '#10b981',
  decayed: '#f59e0b',
  conflicted: '#ef4444',
  archived: '#9ca3af',
}

interface Props {
  node: KnowledgeNode
  onClick?: () => void
}

export function NodeCard({ node, onClick }: Props) {
  const layerColor = LAYER_COLORS[node.layer] ?? '#9ca3af'
  return (
    <div
      onClick={onClick}
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        padding: '12px 14px',
        background: '#fff',
        cursor: onClick ? 'pointer' : 'default',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span
          style={{
            fontSize: 10,
            padding: '1px 7px',
            borderRadius: 99,
            background: layerColor + '18',
            color: layerColor,
            border: `1px solid ${layerColor}40`,
            fontWeight: 500,
          }}
        >
          {LAYER_NAMES[node.layer] ?? `Layer ${node.layer}`}
        </span>
        <span
          style={{
            fontSize: 10,
            padding: '1px 7px',
            borderRadius: 99,
            background: (STATUS_COLORS[node.status] ?? '#9ca3af') + '18',
            color: STATUS_COLORS[node.status] ?? '#9ca3af',
            border: `1px solid ${STATUS_COLORS[node.status] ?? '#9ca3af'}40`,
          }}
        >
          {node.status}
        </span>
        <span style={{ flex: 1 }} />
        <ConfidenceBar value={node.confidence} size="sm" />
      </div>
      <div style={{ fontFamily: 'monospace', fontSize: 12, color: '#374151', fontWeight: 500 }}>
        {node.semantic_id}
      </div>
      <div style={{ fontSize: 12, color: '#6b7280', lineHeight: 1.5 }}>
        {node.semantic_definition}
      </div>
      {node.page_path && (
        <div style={{ fontSize: 11, color: '#9ca3af', fontFamily: 'monospace' }}>
          {node.page_path}
        </div>
      )}
    </div>
  )
}
