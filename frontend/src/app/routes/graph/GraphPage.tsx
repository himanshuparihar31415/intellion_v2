import { useState } from 'react'
import { useNodes, useNode } from '../../../hooks/useGraph'
import { NodeCard } from '../../../components/graph/NodeCard'
import { EdgeList } from '../../../components/graph/EdgeList'
import { ConfidenceBar } from '../../../components/graph/ConfidenceBar'

const LAYERS = [
  { value: undefined, label: 'All layers' },
  { value: 1, label: 'Structural' },
  { value: 2, label: 'Interaction' },
  { value: 3, label: 'Behavioral' },
  { value: 4, label: 'Rule' },
]

interface Props { intellion_id: string }

export function GraphPage({ intellion_id }: Props) {
  const [layer, setLayer] = useState<number | undefined>(undefined)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { data, isLoading } = useNodes(intellion_id, layer)
  const { data: detail } = useNode(selectedId ?? '')

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 16, height: '100%' }}>
      <div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
          {LAYERS.map((l) => (
            <button
              key={String(l.value)}
              onClick={() => setLayer(l.value)}
              style={{
                padding: '4px 12px',
                borderRadius: 99,
                border: '1px solid',
                fontSize: 12,
                cursor: 'pointer',
                background: layer === l.value ? '#6366f1' : '#fff',
                color: layer === l.value ? '#fff' : '#374151',
                borderColor: layer === l.value ? '#6366f1' : '#d1d5db',
              }}
            >
              {l.label}
            </button>
          ))}
        </div>

        {isLoading && <div style={{ color: '#9ca3af', fontSize: 13 }}>Loading…</div>}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {data?.nodes.map((node) => (
            <NodeCard
              key={node.id}
              node={node}
              onClick={() => setSelectedId(node.id === selectedId ? null : node.id)}
            />
          ))}
          {!isLoading && !data?.nodes.length && (
            <div style={{ color: '#9ca3af', fontSize: 13, padding: 24, textAlign: 'center' }}>
              No nodes yet. Start a training session to populate the graph.
            </div>
          )}
        </div>
      </div>

      {/* Detail panel */}
      <div style={{ borderLeft: '1px solid #e5e7eb', paddingLeft: 16, overflowY: 'auto' }}>
        {detail ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <div style={{ fontFamily: 'monospace', fontSize: 14, fontWeight: 600, color: '#111827' }}>
                {detail.node.semantic_id}
              </div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                {detail.node.semantic_definition}
              </div>
            </div>
            <ConfidenceBar value={detail.node.confidence} />
            <div>
              <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6, fontWeight: 500 }}>EDGES</div>
              <EdgeList edges={detail.edges} />
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6, fontWeight: 500 }}>
                SOURCES ({detail.sources.length})
              </div>
              {detail.sources.map((s) => (
                <div
                  key={s.id}
                  style={{
                    fontSize: 11,
                    color: '#6b7280',
                    padding: '4px 0',
                    borderBottom: '1px solid #f3f4f6',
                    display: 'flex',
                    justifyContent: 'space-between',
                  }}
                >
                  <span>{s.source_type}</span>
                  <span style={{ color: s.confidence_delta >= 0 ? '#10b981' : '#ef4444' }}>
                    {s.confidence_delta >= 0 ? '+' : ''}{s.confidence_delta.toFixed(1)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ color: '#9ca3af', fontSize: 13, paddingTop: 40, textAlign: 'center' }}>
            Select a node to inspect
          </div>
        )}
      </div>
    </div>
  )
}
