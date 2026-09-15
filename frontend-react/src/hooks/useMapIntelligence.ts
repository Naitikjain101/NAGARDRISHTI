import { useState, useEffect } from 'react';
import { calculatePriorityScore, type PriorityResult } from '@/lib/priorityScore';

export interface MaintenanceAction {
  id: string;
  status: string;
  assigned_team: string;
  assigned_department: string;
  action_type: string;
  resolution_note?: string;
  created_at: string;
  updated_at?: string;
  assigned_at?: string;
  started_at?: string;
  resolved_at?: string;
  incident_id?: string;
}

export interface MapIncident {
  id: string;
  incident_type: string;
  type?: string; 
  severity: string;
  status: string;
  confidence: number;
  latitude: number;
  longitude: number;
  observation_count: number;
  observed_by: string[];
  unique_journey_count?: number;
  dedup_status: string;
  first_seen_at: string;
  last_seen_at: string;
  timestamp?: number;
  // Phase 6 extensions
  priority_score?: number;
  priority_level?: PriorityResult['level'];
  priority_breakdown?: PriorityResult['breakdown'];
  // Phase 7 extensions
  maintenance_actions?: MaintenanceAction[] | MaintenanceAction;
  action?: MaintenanceAction;
  metadata?: any;
}

export interface MapBus {
  mission_id: string;
  bus_id: string;
  route_name: string;
  current_timestamp: number;
  current_lat: number;
  current_lng: number;
  latitude: number;
  longitude: number;
  speed_kmh: number | null;
  ai_status: string;
  pothole_count: number;
  waterlogging_count: number;
}

export interface FleetSummary {
  fleet: { total_buses: number; active_journeys: number };
  coverage: { total_route_km: number; observed_route_km: number; coverage_percent: number };
  incidents: { total: number; open: number; validated: number; confirmed: number; critical: number };
}

export function useMapIntelligence() {
  const [incidents, setIncidents] = useState<MapIncident[]>([]);
  const [buses, setBuses] = useState<MapBus[]>([]);
  const [summary, setSummary] = useState<FleetSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function fetchMapState() {
      try {
        const [incRes, busesRes, summaryRes] = await Promise.all([
          fetch('/api/map/incidents'),
          fetch('/api/map/buses'),
          fetch('/api/buses/analytics/summary').catch(() => null)
        ]);
        
        if (!mounted) return;
        
        const incData = await incRes.json();
        const busData = await busesRes.json();
        
        if (summaryRes && summaryRes.ok) {
          const sumData = await summaryRes.json();
          setSummary(sumData);
        }

        // Compute priority for all incidents
        let incidentsList = Array.isArray(incData) ? incData : (incData.incidents || []);
        let busList = Array.isArray(busData) ? busData : (busData?.buses || []);
        
        let enhancedIncidents = incidentsList.map((inc: any) => {
          const priority = calculatePriorityScore(inc);
          
          let action: MaintenanceAction | undefined = undefined;
          if (inc.maintenance_actions) {
             if (Array.isArray(inc.maintenance_actions) && inc.maintenance_actions.length > 0) {
                 action = inc.maintenance_actions[0];
             } else if (!Array.isArray(inc.maintenance_actions)) {
                 action = inc.maintenance_actions as MaintenanceAction;
             }
          }

          return {
            ...inc,
            priority_score: priority.score,
            priority_level: priority.level,
            priority_breakdown: priority.breakdown,
            action: action
          };
        });

        // Ensure Priority Queue logic is supported by setting enhanced list.
        // We do NOT filter out resolved incidents from here so that Action Center can still see them.
        // Priority Queue and Action Center will filter them based on their respective rules.
        setIncidents(enhancedIncidents);
        setBuses(busList);
      } catch (error) {
        console.error('Failed to fetch map intelligence:', error);
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    fetchMapState();
    const interval = setInterval(fetchMapState, 5000); // Polling for real-time live map
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return { incidents, buses, summary, isLoading };
}

export interface IncidentEvidence {
  incident_id: string;
  incident_type: string;
  severity: string;
  latitude: number;
  longitude: number;
  observation_count: number;
  observed_by: string[];
  dedup_status: string;
  observations: {
    id: string;
    mission_id: string;
    bus_id: string;
    video_timestamp: number;
    confidence: number;
    bbox: number[] | null;
    created_at: string;
    route_name?: string;
    video_filename?: string;
  }[];
}

// Separate hook for evidence fetching since it happens on demand
export function useIncidentEvidence() {
  const [evidence, setEvidence] = useState<IncidentEvidence | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchEvidence = async (incidentId: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/incidents/${incidentId}/evidence`);
      if (!res.ok) throw new Error('Failed to fetch evidence');
      const data = await res.json();
      setEvidence(data);
    } catch (err) {
      console.error(err);
      setEvidence(null);
    } finally {
      setIsLoading(false);
    }
  };

  const clearEvidence = () => setEvidence(null);

  return { evidence, isLoading, fetchEvidence, clearEvidence };
}
