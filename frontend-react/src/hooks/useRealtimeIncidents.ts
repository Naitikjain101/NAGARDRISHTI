import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { incidentsApi, type Incident, type IncidentsResponse } from '@/api/incidents';
import { supabase } from '@/lib/supabase';

export function useRealtimeIncidents(filters?: { status?: string; type?: string; severity?: string; limit?: number }) {
  const queryClient = useQueryClient();
  const queryKey = ['incidents', filters];

  // 1. Fetch initial data via React Query
  const query = useQuery({
    queryKey,
    queryFn: () => incidentsApi.getIncidents(filters),
    staleTime: Infinity, // Rely on realtime for updates, but keep polling as fallback
    refetchInterval: 5000,
  });

  // 2. Setup Realtime subscription
  useEffect(() => {
    // Note: To subscribe to the `incidents` table, it must have Realtime enabled in Supabase.
    // SQL: ALTER PUBLICATION supabase_realtime ADD TABLE incidents;
    
    const channelId = `incidents-${Date.now()}-${Math.random()}`;
    const channel = supabase
      .channel(channelId)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'incidents' },
        (payload) => {
          // When a change occurs in Supabase, we update the React Query cache dynamically
          
          queryClient.setQueryData(queryKey, (oldData: IncidentsResponse | undefined) => {
            if (!oldData) return oldData;

            const newIncidents = [...oldData.incidents];
            
            if (payload.eventType === 'INSERT') {
              // Convert DB record to API format (simplistic mapping for the frontend cache)
              const newRecord = payload.new as any;
              const incident: Incident = {
                id: newRecord.id,
                video_id: newRecord.video_id,
                type: newRecord.incident_type,
                class_name: newRecord.incident_type, // simplified
                canonical_capability: newRecord.incident_type,
                confidence: newRecord.confidence,
                composite_score: newRecord.composite_score,
                severity: newRecord.severity,
                timestamp: newRecord.timestamp,
                frame: newRecord.frame_number,
                occurrence_count: 1,
                bbox: newRecord.bbox,
                gps_available: newRecord.latitude !== null,
                latitude: newRecord.latitude,
                longitude: newRecord.longitude,
                gps_accuracy_meters: null,
                road_segment_id: null,
                status: newRecord.status,
                suppression_reason: null,
                track_id: newRecord.track_id,
                created_at: newRecord.created_at,
              };
              
              // Only add if it matches filters (basic check)
              if (filters?.status && incident.status !== filters.status) return oldData;
              
              newIncidents.unshift(incident);
            } 
            else if (payload.eventType === 'UPDATE') {
              const index = newIncidents.findIndex(i => i.id === payload.new.id);
              if (index !== -1) {
                // Update specific fields
                newIncidents[index] = { ...newIncidents[index], ...payload.new, type: payload.new.incident_type || newIncidents[index].type };
              }
            }
            else if (payload.eventType === 'DELETE') {
              const index = newIncidents.findIndex(i => i.id === payload.old.id);
              if (index !== -1) {
                newIncidents.splice(index, 1);
              }
            }

            return {
              ...oldData,
              incidents: newIncidents,
              total: payload.eventType === 'INSERT' ? oldData.total + 1 : (payload.eventType === 'DELETE' ? oldData.total - 1 : oldData.total)
            };
          });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [queryClient, queryKey, filters]);

  return query;
}
