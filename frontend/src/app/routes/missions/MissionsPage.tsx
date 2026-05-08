import { useState } from 'react'
import { useReason, useRunMission } from '../../../hooks/useMission'
import { TestPlan } from '../../../lib/api'
import { ConfidenceBar } from '../../../components/graph/ConfidenceBar'

interface Props { intellion_id: string }

const STEP_TYPE_COLORS = {
  confirm: { bg: '#dcfce7', color: '#166534', border: '#86efac' },
  verify:  { bg: '#fef9c3', color: '#854d0e', border: '#fde047' },
  discover:{ bg: '#ede9fe', color: '#4c1d95', border: '#c4b5fd' },
}

export function MissionsPage({ intellion_id }: Props) {
  const [task, setTask] = useState('')
  const [plan, setPlan] = useState<TestPlan | null>(null)

  const reason = useReason(intellion_id)
  const { start, status, missionId } = useRunMission(intellion_id)

  const missionData = status.data as Record<string, unknown> | undefined

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 760 }}>
      {/* Task input */}
      <section style={card}>
        <h3 style={cardTitle}>Mission Planner</h3>
        <p style={cardDesc}>
          Describe what to test in plain English. The reasoning engine will traverse the knowledge
          graph and produce a structured test plan.
        </p>
        <textarea
          placeholder={`e.g. "Validate the checkout flow for guest users in the UK region"`}
          value={task}
          onChange={(e) => setTask(e.target.value)}
          rows={3}
          style={{ ...inputStyle, resize: 'vertical' }}
        />
        <button
          onClick={() => reason.mutate(task, { onSuccess: (r) => setPlan(r.plan) })}
          disabled={reason.isPending || !task.trim()}
          style={primaryBtn}
        >
          {reason.isPending ? 'Reasoning…' : 'Generate Plan'}
        </button>
      </section>

      {/* Plan */}
      {plan && (
        <section style={card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <h3 style={cardTitle}>{plan.task_description}</h3>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                {plan.total_nodes_in_scope} nodes in scope · {plan.gap_count} gaps ·{' '}
                {plan.conflict_count} conflicts · est. +{plan.estimated_coverage_gain.toFixed(0)}% coverage
              </div>
            </div>
            <button
              onClick={() => start.mutate(plan)}
              disabled={start.isPending}
              style={{ ...primaryBtn, background: '#10b981' }}
            >
              {start.isPending ? 'Launching…' : 'Run Mission'}
            </button>
          </div>

          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {plan.steps.map((step) => {
              const colors = STEP_TYPE_COLORS[step.step_type]
              return (
                <div
                  key={step.step_number}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    padding: '10px 0',
                    borderBottom: '1px solid #f3f4f6',
                  }}
                >
                  <div
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: '50%',
                      background: '#eef2ff',
                      color: '#6366f1',
                      fontSize: 11,
                      fontWeight: 600,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    {step.step_number}
                  </div>
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <span style={{ fontSize: 13, color: '#111827' }}>{step.description}</span>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <span
                        style={{
                          fontSize: 10,
                          padding: '1px 7px',
                          borderRadius: 99,
                          background: colors.bg,
                          color: colors.color,
                          border: `1px solid ${colors.border}`,
                        }}
                      >
                        {step.step_type}
                      </span>
                      <span style={{ fontSize: 10, color: '#9ca3af' }}>{step.skill_hint}</span>
                    </div>
                  </div>
                  <ConfidenceBar value={step.confidence} size="sm" />
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Mission status */}
      {missionId && (
        <section style={card}>
          <h3 style={cardTitle}>Mission Status</h3>
          {missionData?.status === 'running' && (
            <div style={{ fontSize: 13, color: '#6b7280' }}>Running…</div>
          )}
          {missionData?.status === 'completed' && (
            <>
              <div
                style={{
                  fontSize: 13,
                  color: missionData.success ? '#10b981' : '#ef4444',
                  fontWeight: 500,
                }}
              >
                {missionData.success ? 'Mission passed' : 'Mission found deviations'}
              </div>
              <div style={{ fontSize: 12, color: '#6b7280' }}>
                {String(missionData.steps_executed)} steps · Sync:{' '}
                {JSON.stringify(missionData.sync_summary)}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
                {((missionData.findings as Array<Record<string, unknown>>) ?? []).map((f, i) => {
                  const typeColors: Record<string, string> = {
                    confirmed: '#10b981',
                    logic_deviation: '#ef4444',
                    discovery: '#8b5cf6',
                  }
                  return (
                    <div
                      key={i}
                      style={{
                        fontSize: 12,
                        color: '#374151',
                        padding: '6px 10px',
                        background: '#f9fafb',
                        borderRadius: 6,
                        borderLeft: `3px solid ${typeColors[String(f.type)] ?? '#e5e7eb'}`,
                      }}
                    >
                      <span style={{ color: typeColors[String(f.type)], fontWeight: 500 }}>
                        {String(f.type)}
                      </span>{' '}
                      — {String(f.description)}
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </section>
      )}
    </div>
  )
}

const card: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 10,
  padding: '16px 18px',
  background: '#fff',
  display: 'flex',
  flexDirection: 'column',
  gap: 10,
}
const cardTitle: React.CSSProperties = { fontSize: 14, fontWeight: 600, color: '#111827', margin: 0 }
const cardDesc: React.CSSProperties = { fontSize: 13, color: '#6b7280', margin: 0, lineHeight: 1.55 }
const inputStyle: React.CSSProperties = {
  border: '1px solid #d1d5db',
  borderRadius: 6,
  padding: '7px 10px',
  fontSize: 13,
  color: '#111827',
  background: '#fff',
  width: '100%',
}
const primaryBtn: React.CSSProperties = {
  background: '#6366f1',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '8px 16px',
  fontSize: 13,
  cursor: 'pointer',
  fontWeight: 500,
  alignSelf: 'flex-start',
}
