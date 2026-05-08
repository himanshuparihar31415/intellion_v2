const BASE = import.meta.env.VITE_API_URL ?? '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface Intellion {
  id: string
  name: string
  target_url: string
  created_at: string
}

export interface KnowledgeNode {
  id: string
  intellion_id: string
  layer: number
  semantic_id: string
  semantic_definition: string
  page_path: string | null
  confidence: number
  status: string
  verify_due_at: string | null
  updated_at: string
}

export interface NodeSource {
  id: string
  node_id: string
  source_type: string
  source_weight: number
  confidence_delta: number
  session_id: string
  created_at: string
}

export interface GraphEdge {
  id: string
  source_node_id: string
  target_node_id: string
  edge_type: string
  confidence: number | null
}

export interface Conflict {
  id: string
  node_id: string
  source_a_claim: string
  source_b_claim: string
  severity: string
  auto_resolvable: boolean
  resolution_type: string | null
  created_at: string
}

export interface TestStep {
  step_number: number
  description: string
  step_type: 'confirm' | 'verify' | 'discover'
  skill_hint: string
  confidence: number
}

export interface TestPlan {
  plan_id: string
  intellion_id: string
  task_description: string
  steps: TestStep[]
  total_nodes_in_scope: number
  gap_count: number
  conflict_count: number
  estimated_coverage_gain: number
}

export interface ReasoningResult {
  plan: TestPlan
  scope_nodes: Array<{ semantic_id: string; annotation: string; confidence: number }>
  hypotheses: Array<{ description: string; step_type: string; confidence: number }>
  skipped_node_ids: string[]
}

export interface Session {
  id: string
  intellion_id: string
  session_type: string
  status: string
  coverage_score: number | null
  created_at: string
}

// ── Intellions ────────────────────────────────────────────────────────────────

export const api = {
  intellions: {
    create: (name: string, target_url: string) =>
      request<Intellion>('/intellions', {
        method: 'POST',
        body: JSON.stringify({ name, target_url }),
      }),
    get: (id: string) => request<Intellion>(`/intellions/${id}`),
  },

  graph: {
    nodes: (intellion_id: string, layer?: number, page = 0) =>
      request<{ nodes: KnowledgeNode[] }>(
        `/graph/nodes?intellion_id=${intellion_id}${layer != null ? `&layer=${layer}` : ''}&page=${page}`
      ),
    node: (id: string) =>
      request<{ node: KnowledgeNode; sources: NodeSource[]; edges: GraphEdge[] }>(
        `/graph/nodes/${id}`
      ),
    conflicts: (intellion_id: string) =>
      request<{ conflicts: Conflict[] }>(`/graph/conflicts?intellion_id=${intellion_id}`),
    resolveConflict: (id: string, resolution: string) =>
      request(`/graph/conflicts/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ resolution }),
      }),
  },

  training: {
    teach: (intellion_id: string, semantic_id: string, fact: string, layer: number) =>
      request('/training/teach', {
        method: 'POST',
        body: JSON.stringify({ intellion_id, semantic_id, fact, layer }),
      }),
    ingestSchema: (intellion_id: string, content: string, schema_type: string) =>
      request('/training/ingest/schema', {
        method: 'POST',
        body: JSON.stringify({ intellion_id, content, schema_type }),
      }),
    startExploration: (intellion_id: string) =>
      request<{ session_id: string; status: string }>('/training/explore/start', {
        method: 'POST',
        body: JSON.stringify({ intellion_id }),
      }),
    explorationStatus: (session_id: string) =>
      request<{ status: string; steps_taken: number; nodes_written: number }>(
        `/training/explore/${session_id}/status`
      ),
  },

  reasoning: {
    reason: (intellion_id: string, task: string) =>
      request<ReasoningResult>('/reason', {
        method: 'POST',
        body: JSON.stringify({ intellion_id, task }),
      }),
  },

  missions: {
    run: (intellion_id: string, plan: TestPlan) =>
      request<{ mission_id: string; status: string }>('/missions', {
        method: 'POST',
        body: JSON.stringify({ intellion_id, plan }),
      }),
    get: (mission_id: string) => request<Record<string, unknown>>(`/missions/${mission_id}`),
  },

  sessions: {
    list: (intellion_id: string) =>
      request<{ sessions: Session[] }>(`/sessions?intellion_id=${intellion_id}`),
    analytics: (intellion_id: string) =>
      request(`/sessions/analytics?intellion_id=${intellion_id}`),
  },

  webhooks: {
    deploy: (intellion_id: string, deploy_reference: string) =>
      request('/webhooks/deploy', {
        method: 'POST',
        body: JSON.stringify({ intellion_id, deploy_reference }),
      }),
  },
}
