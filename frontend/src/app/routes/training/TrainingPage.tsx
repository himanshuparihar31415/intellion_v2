import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../../../lib/api'

interface Props { intellion_id: string }

export function TrainingPage({ intellion_id }: Props) {
  const [teachForm, setTeachForm] = useState({ semantic_id: '', fact: '', layer: 4 })
  const [schemaForm, setSchemaForm] = useState({ content: '', schema_type: 'openapi' })
  const [exploreSession, setExploreSession] = useState<string | null>(null)

  const teach = useMutation({
    mutationFn: () =>
      api.training.teach(intellion_id, teachForm.semantic_id, teachForm.fact, teachForm.layer),
    onSuccess: () => setTeachForm({ semantic_id: '', fact: '', layer: 4 }),
  })

  const ingestSchema = useMutation({
    mutationFn: () =>
      api.training.ingestSchema(intellion_id, schemaForm.content, schemaForm.schema_type),
    onSuccess: () => setSchemaForm((f) => ({ ...f, content: '' })),
  })

  const explore = useMutation({
    mutationFn: () => api.training.startExploration(intellion_id),
    onSuccess: (data) => setExploreSession(data.session_id),
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 680 }}>
      {/* Exploration */}
      <section style={card}>
        <h3 style={cardTitle}>Guided Exploration</h3>
        <p style={cardDesc}>
          Launch a Playwright agent to crawl the target app and populate the knowledge graph with
          structural and interaction nodes.
        </p>
        <button onClick={() => explore.mutate()} disabled={explore.isPending} style={primaryBtn}>
          {explore.isPending ? 'Starting…' : 'Start Exploration'}
        </button>
        {exploreSession && (
          <div style={{ marginTop: 10, fontSize: 12, color: '#6b7280' }}>
            Session started: <code>{exploreSession}</code>
          </div>
        )}
      </section>

      {/* Human teaching */}
      <section style={card}>
        <h3 style={cardTitle}>Human Teaching</h3>
        <p style={cardDesc}>
          Directly assert a fact about the app. Written at 95% confidence — highest trust source.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <input
            placeholder="semantic_id (e.g. rule_admin_timeout)"
            value={teachForm.semantic_id}
            onChange={(e) => setTeachForm((f) => ({ ...f, semantic_id: e.target.value }))}
            style={inputStyle}
          />
          <textarea
            placeholder="Fact (e.g. Admin sessions expire after 15 minutes of inactivity)"
            value={teachForm.fact}
            onChange={(e) => setTeachForm((f) => ({ ...f, fact: e.target.value }))}
            rows={3}
            style={{ ...inputStyle, resize: 'vertical' }}
          />
          <select
            value={teachForm.layer}
            onChange={(e) => setTeachForm((f) => ({ ...f, layer: Number(e.target.value) }))}
            style={inputStyle}
          >
            <option value={1}>Structural</option>
            <option value={2}>Interaction</option>
            <option value={3}>Behavioral</option>
            <option value={4}>Rule</option>
          </select>
          <button
            onClick={() => teach.mutate()}
            disabled={teach.isPending || !teachForm.semantic_id || !teachForm.fact}
            style={primaryBtn}
          >
            {teach.isPending ? 'Writing…' : 'Teach'}
          </button>
          {teach.isSuccess && (
            <div style={{ fontSize: 12, color: '#10b981' }}>Node written successfully.</div>
          )}
        </div>
      </section>

      {/* Schema ingestion */}
      <section style={card}>
        <h3 style={cardTitle}>Schema Ingestion</h3>
        <p style={cardDesc}>Paste an OpenAPI spec, GraphQL SDL, or SQL DDL to ingest at 80% confidence.</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <select
            value={schemaForm.schema_type}
            onChange={(e) => setSchemaForm((f) => ({ ...f, schema_type: e.target.value }))}
            style={inputStyle}
          >
            <option value="openapi">OpenAPI / Swagger</option>
            <option value="graphql">GraphQL SDL</option>
            <option value="sql">SQL DDL</option>
          </select>
          <textarea
            placeholder="Paste schema content here…"
            value={schemaForm.content}
            onChange={(e) => setSchemaForm((f) => ({ ...f, content: e.target.value }))}
            rows={8}
            style={{ ...inputStyle, fontFamily: 'monospace', fontSize: 11, resize: 'vertical' }}
          />
          <button
            onClick={() => ingestSchema.mutate()}
            disabled={ingestSchema.isPending || !schemaForm.content}
            style={primaryBtn}
          >
            {ingestSchema.isPending ? 'Ingesting…' : 'Ingest Schema'}
          </button>
          {ingestSchema.isSuccess && (
            <div style={{ fontSize: 12, color: '#10b981' }}>
              Schema ingested: {JSON.stringify((ingestSchema.data as Record<string, unknown>))}
            </div>
          )}
        </div>
      </section>
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
