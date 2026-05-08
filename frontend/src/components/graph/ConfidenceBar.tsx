interface Props {
  value: number
  size?: 'sm' | 'md'
}

const COLORS: [number, string][] = [
  [80, '#22c55e'],
  [60, '#f59e0b'],
  [40, '#f97316'],
  [0,  '#ef4444'],
]

function color(v: number) {
  return (COLORS.find(([threshold]) => v >= threshold) ?? COLORS[COLORS.length - 1])[1]
}

export function ConfidenceBar({ value, size = 'md' }: Props) {
  const h = size === 'sm' ? 4 : 6
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div
        style={{
          width: size === 'sm' ? 60 : 80,
          height: h,
          background: '#e5e7eb',
          borderRadius: h,
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: `${Math.min(100, Math.max(0, value))}%`,
            height: '100%',
            background: color(value),
            borderRadius: h,
            transition: 'width 0.3s',
          }}
        />
      </div>
      <span style={{ fontSize: size === 'sm' ? 11 : 12, color: '#6b7280', minWidth: 28 }}>
        {Math.round(value)}%
      </span>
    </div>
  )
}
