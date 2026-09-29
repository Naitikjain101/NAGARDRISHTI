import type { MapIncident } from '@/hooks/useMapIntelligence';

export interface PriorityBreakdown {
  severity: number;
  fleetEvidence: number;
  observationFrequency: number;
  persistence: number;
  total: number;
}

export interface PriorityResult {
  score: number;
  level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  breakdown: PriorityBreakdown;
}

export function calculatePriorityScore(incident: Partial<MapIncident>): PriorityResult {
  // A. Severity - MAX 40
  let severityScore = 0;
  const sev = (incident.severity || 'LOW').toUpperCase();
  if (sev === 'CRITICAL') severityScore = 40;
  else if (sev === 'HIGH') severityScore = 30;
  else if (sev === 'MODERATE' || sev === 'MEDIUM') severityScore = 20;
  else severityScore = 10; // LOW or unknown

  // B. Detection Evidence - MAX 25
  let fleetEvidenceScore = 0;
  const uniqueBuses = incident.observed_by?.length || 0;
  if (uniqueBuses === 1) fleetEvidenceScore = 10;
  else if (uniqueBuses === 2) fleetEvidenceScore = 15;
  else if (uniqueBuses >= 3) fleetEvidenceScore = 25;

  // C. Observation Frequency - MAX 20
  const obsCount = incident.observation_count || 0;
  const observationFrequencyScore = Math.min(obsCount * 2, 20);

  // D. Persistence - MAX 15
  let persistenceScore = 0;
  if (incident.first_seen_at) {
    const firstSeen = new Date(incident.first_seen_at).getTime();
    const current = incident.last_seen_at ? new Date(incident.last_seen_at).getTime() : Date.now();
    const daysSince = Math.max(0, (current - firstSeen) / (1000 * 60 * 60 * 24));
    persistenceScore = Math.min(daysSince * 3, 15);
  }

  // Enforce bounds (0-100) and round
  let total = Math.round(severityScore + fleetEvidenceScore + observationFrequencyScore + persistenceScore);
  total = Math.max(0, Math.min(100, total));

  // Determine Level
  let level: PriorityResult['level'] = 'LOW';
  if (total >= 75) level = 'CRITICAL';
  else if (total >= 50) level = 'HIGH';
  else if (total >= 25) level = 'MEDIUM';

  return {
    score: total,
    level,
    breakdown: {
      severity: severityScore,
      fleetEvidence: fleetEvidenceScore,
      observationFrequency: observationFrequencyScore,
      persistence: Math.round(persistenceScore * 10) / 10, // Round for display
      total
    }
  };
}
