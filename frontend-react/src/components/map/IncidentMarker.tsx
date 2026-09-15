import { Marker, Popup, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import type { MapIncident } from '@/hooks/useMapIntelligence';

interface IncidentMarkerProps {
  incident: MapIncident;
  onClick: (incident: MapIncident) => void;
}

/** Build a high-visibility custom icon SVG for each incident type */
function buildIcon(incident: MapIncident): L.DivIcon {
  const type = (incident.incident_type || incident.type || '').toLowerCase();
  const severity = (incident.severity || 'LOW').toUpperCase();
  const isConfirmed = incident.dedup_status === 'CONFIRMED';
  const busCount = incident.observed_by?.length || 1;

  let primary = '#ef4444';   // red — pothole default
  let icon = '🕳️';

  if (incident.status === 'RESOLVED') {
    primary = '#6b7280';     // grey
    icon = '✅';
  } else if (type === 'waterlogging') {
    primary = '#3b82f6';     // blue
    icon = '💧';
  } else if (type === 'pothole') {
    // Severity modifies shade but stays in RED family
    if (severity === 'CRITICAL') { primary = '#b91c1c'; }
    else if (severity === 'HIGH') { primary = '#dc2626'; }
    else if (severity === 'MODERATE') { primary = '#f97316'; icon = '⚠️'; }
  }

  const ringColor = isConfirmed ? '#10b981' : primary;
  const hasBadge = busCount >= 2;

  const html = `
    <div style="position:relative; width:24px; height:24px; display:flex; flex-direction:column; align-items:center;">
      <!-- Inner marker circle -->
      <div style="
        position:absolute; top:2px; left:50%; transform:translateX(-50%);
        width:20px; height:20px; border-radius:50%;
        background:${primary};
        border:2px solid white;
        box-shadow:0 1px 4px rgba(0,0,0,0.5);
        display:flex; align-items:center; justify-content:center;
        font-size:10px; line-height:1;
        z-index:10;
      ">${icon}</div>
      <!-- Severity ring arc at bottom -->
      <div style="
        position:absolute; bottom:0; left:50%; transform:translateX(-50%);
        width:8px; height:4px; border-radius:2px;
        background:${ringColor};
        opacity:0.85;
      "></div>
      ${hasBadge ? `
        <!-- Multi-bus badge -->
        <div style="
          position:absolute; top:-4px; right:-4px;
          background:#f97316; color:white;
          font-size:8px; font-weight:900; font-family:monospace;
          border-radius:99px; padding:0 3px;
          border:1px solid white;
          box-shadow:0 1px 2px rgba(0,0,0,0.3);
          z-index:20; line-height:12px;
        ">${busCount}</div>
      ` : ''}
    </div>
  `;

  return L.divIcon({
    html,
    className: 'incident-custom-icon',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
    tooltipAnchor: [12, -12],
  });
}

export function IncidentMarker({ incident, onClick }: IncidentMarkerProps) {
  if (!incident.latitude || !incident.longitude) return null;

  const type = (incident.incident_type || incident.type || 'Unknown');
  const typeLabel = type.replace('_', ' ').toUpperCase();
  const isConfirmed = incident.dedup_status === 'CONFIRMED';
  const uniqueBuses = incident.observed_by?.length || 1;
  const isWaterlogging = type === 'waterlogging';

  let evidenceColor = '#60a5fa';
  if (uniqueBuses === 2) { evidenceColor = '#f97316'; }
  else if (uniqueBuses >= 3) { evidenceColor = '#10b981'; }

  const icon = buildIcon(incident);

  return (
    <Marker
      position={[incident.latitude, incident.longitude]}
      icon={icon}
      eventHandlers={{ click: () => onClick(incident) }}
    >
      {/* Persistent label visible at closer zoom levels */}
      <Tooltip
        direction="right"
        offset={[8, -28]}
        opacity={0.95}
        className="incident-tooltip"
        permanent={false}
      >
        <div style={{ fontFamily: 'Inter, system-ui, sans-serif', minWidth: 130 }}>
          <div style={{ fontWeight: 800, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>
            {typeLabel}
            {isWaterlogging && <span style={{ fontSize: 9, marginLeft: 4, color: '#93c5fd' }}>TEST MODE</span>}
          </div>
          <div style={{ fontSize: 10, opacity: 0.75, marginTop: 2 }}>
            {incident.severity} · {Math.round((incident.confidence || 0) * 100)}% conf
          </div>
          {incident.observation_count > 0 && (
            <div style={{ fontSize: 10, opacity: 0.65 }}>{incident.observation_count} observations</div>
          )}
        </div>
      </Tooltip>

      {/* Click popup */}
      <Popup className="custom-popup" closeButton={false}>
        <div style={{
          padding: 12, minWidth: 220, fontFamily: 'Inter, system-ui, sans-serif',
          background: 'hsl(var(--card)/0.98)', backdropFilter: 'blur(12px)',
          borderRadius: 12, border: '1px solid hsl(var(--border)/0.5)',
          color: 'hsl(var(--foreground))'
        }}>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, paddingBottom: 8, borderBottom: '1px solid hsl(var(--border)/0.4)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 16 }}>{isWaterlogging ? '💧' : '🕳️'}</span>
              <span style={{ fontWeight: 800, fontSize: 14, textTransform: 'capitalize' }}>
                {typeLabel}
                {isWaterlogging && <span style={{ fontSize: 9, marginLeft: 6, color: '#60a5fa', fontWeight: 700 }}>TEST MODE</span>}
              </span>
            </div>
            {isConfirmed && (
              <span style={{ fontSize: 9, fontWeight: 700, background: '#10b98122', color: '#10b981', padding: '2px 6px', borderRadius: 4, textTransform: 'uppercase', letterSpacing: 1 }}>
                ✓ CONFIRMED
              </span>
            )}
          </div>

          {/* Stats grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
            {[
              { label: 'Severity', value: incident.severity },
              { label: 'Confidence', value: `${Math.round((incident.confidence || 0) * 100)}%` },
              { label: 'Sightings', value: incident.observation_count },
              { label: 'Buses', value: uniqueBuses },
            ].map(({ label, value }) => (
              <div key={label} style={{ background: 'hsl(var(--secondary)/0.4)', borderRadius: 6, padding: '4px 6px' }}>
                <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.8, opacity: 0.6 }}>{label}</div>
                <div style={{ fontSize: 12, fontWeight: 700, marginTop: 1 }}>{value}</div>
              </div>
            ))}
          </div>

          {/* Evidence strength bar */}
          <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.8, opacity: 0.6, marginBottom: 4 }}>Evidence Strength</div>
          <div style={{ background: 'hsl(var(--secondary)/0.5)', borderRadius: 4, height: 6, marginBottom: 10 }}>
            <div style={{
              height: '100%', borderRadius: 4, background: evidenceColor,
              width: uniqueBuses === 1 ? '33%' : uniqueBuses === 2 ? '66%' : '100%',
              transition: 'width 0.5s ease'
            }} />
          </div>

          {/* GPS */}
          <div style={{ fontSize: 9, fontFamily: 'monospace', opacity: 0.55, marginBottom: 10 }}>
            {incident.latitude.toFixed(5)}, {incident.longitude.toFixed(5)}
          </div>

          {/* CTA */}
          <button
            onClick={(e) => { e.stopPropagation(); onClick(incident); }}
            style={{
              width: '100%', padding: '6px 0',
              background: 'hsl(var(--primary))', color: 'hsl(var(--primary-foreground))',
              border: 'none', borderRadius: 6, fontSize: 10, fontWeight: 700,
              letterSpacing: 1, textTransform: 'uppercase', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4
            }}
          >
            📋 View Evidence Trail
          </button>
        </div>
      </Popup>
    </Marker>
  );
}
