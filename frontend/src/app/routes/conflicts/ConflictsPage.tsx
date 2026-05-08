import { useConflicts, useResolveConflict } from '../../../hooks/useGraph'

interface Props { intellion_id: string }

const SEVERITY_COLORS: Record<string, { bg: string; color: string; border: string }> = {
  critical: { bg: '#fef2f2', color: '#991b1b', border: '#fca5a5' },
  high:     { bg: '#fff7ed', color: '#9a3412', border: '#fdba74' },
  medium:   { bg: '#fefce8', color: '#854d0e', border: '#fde68a' },
  low:      { bg: '#f0fdf4', color: '#166534', border: '#86efac' },
}

const RESOLUTIONS = [
  { value: 'winner_a', label: 'Accept A (higher trust)' },
  { value: 'winner_b', label: 'Accept B (challenger)' },
  { value: 'both_wrong', label: 'Both wrong — discard' },
  { value: 'intentional', label: 'Intentional difference' },
]

export function ConflictsPage({ intellion_id }: Props) {
  const { data, isLoading } = useConflicts(intellion_id)
  const resolve = useResolveConflict(intellion_id)

  if (isLoading) return <div style={{ color: '#9ca3af', fontSize: 13 }}>Loading…</div>

  const conflicts = data?.conflicts ?? []

  if (!conflicts.length) {
    return (
      <div style={{ color: '#9ca3af', fontSize: 13, padding: 40, textAlign: 'center' }}>
        No unresolved conflicts.
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 760 }}>
      <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 4 }}>
        {conflicts.length} unresolved conflict{conflicts.length !== 1 ? 's' : ''}
      </div>
      {conflicts.map((c) => {
        const sev = SEVERITY_COLORS[c.severity] ?? SEVERITY_COLORS.low
        return (
          <div
            key={c.id}
            style={{
              border: `1px solid ${sev.border}`,
              borderRadius: 10,
              background: sev.bg,
              padding: '14px 16px',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span
                style={{
                  fontSize: 10,
                  padding: '1px 7px',
                  borderRadius: 99,
                  background: sev.bg,
                  color: sev.color,
                  border: `1px solid ${sev.border}`,
                  fontWeight: 600,
                }}
              >
                {c.severity.toUpperCase()}
              </span>
              {c.auto_resolvable && (
                <span style={{ fontSize: 10, color: '#6b7280', padding: '1px 7px', border: '1px solid #d1d5db', borderRadius: 99 }}>
                  auto-resolvable
                </span>
              )}
              <span style={{ fontSize: 11, color: '#9ca3af', marginLeft: 'auto' }}>
                {new Date(c.created_at).toLocaleDateString()}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {[
                { label: 'Claim A', text: c.source_a_claim },
                { label: 'Claim B', text: c.source_b_claim },
              ].map(({ label, text }) => (
                <div
                  key={label}
                  style={{
                    background: 'rgba(255,255,255,0.7)',
                    borderRadius: 6,
                    padding: '8px 10px',
                    fontSize: 12,
                    color: '#374151',
                    lineHeight: 1.5,
                  }}
                >
                  <div style={{ fontSize: 10, color: '#9ca3af', marginBottom: 4, fontWeight: 500 }}>{label}</div>
                  {text}
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {RESOLUTIONS.map((r) => (
                <button
                  key={r.value}
                  onClick={() => resolve.mutate({ id: c.id, resolution: r.value })}
                  disabled={resolve.isPending}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    borderRadius: 6,
                    border: '1px solid #d1d5db',
                    background: '#fff',
                    cursor: 'pointer',
                    color: '#374151',
                  }}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
