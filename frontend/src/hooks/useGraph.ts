import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

export function useNodes(intellion_id: string, layer?: number) {
  return useQuery({
    queryKey: ['nodes', intellion_id, layer],
    queryFn: () => api.graph.nodes(intellion_id, layer),
    enabled: !!intellion_id,
  })
}

export function useNode(id: string) {
  return useQuery({
    queryKey: ['node', id],
    queryFn: () => api.graph.node(id),
    enabled: !!id,
  })
}

export function useConflicts(intellion_id: string) {
  return useQuery({
    queryKey: ['conflicts', intellion_id],
    queryFn: () => api.graph.conflicts(intellion_id),
    enabled: !!intellion_id,
    refetchInterval: 30_000,
  })
}

export function useResolveConflict(intellion_id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, resolution }: { id: string; resolution: string }) =>
      api.graph.resolveConflict(id, resolution),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['conflicts', intellion_id] }),
  })
}
