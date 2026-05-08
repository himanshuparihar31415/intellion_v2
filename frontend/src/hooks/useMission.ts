import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api, TestPlan, ReasoningResult } from '../lib/api'

export function useReason(intellion_id: string) {
  return useMutation({
    mutationFn: (task: string) => api.reasoning.reason(intellion_id, task),
  })
}

export function useRunMission(intellion_id: string) {
  const [missionId, setMissionId] = useState<string | null>(null)
  const start = useMutation({
    mutationFn: (plan: TestPlan) => api.missions.run(intellion_id, plan),
    onSuccess: (data) => setMissionId(data.mission_id),
  })
  const status = useQuery({
    queryKey: ['mission', missionId],
    queryFn: () => api.missions.get(missionId!),
    enabled: !!missionId,
    refetchInterval: (data) => {
      const d = data?.state?.data as Record<string, unknown> | undefined
      return d?.status === 'running' ? 2000 : false
    },
  })
  return { start, status, missionId }
}

export function useSessions(intellion_id: string) {
  return useQuery({
    queryKey: ['sessions', intellion_id],
    queryFn: () => api.sessions.list(intellion_id),
    enabled: !!intellion_id,
  })
}
