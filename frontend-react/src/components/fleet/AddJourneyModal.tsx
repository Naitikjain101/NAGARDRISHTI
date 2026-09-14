import React, { useState, useRef, useEffect, useCallback } from 'react';
import { X, Upload, Video, FileVideo, CheckCircle2, AlertCircle, Loader2, MapPin, Navigation, Search } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { LocationService, type LocationSearchResult, type RouteResult } from '@/services/LocationService';
import { MapContainer, TileLayer, Marker, Polyline, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';

function MapClickEvents({ onMapClick }: { onMapClick: (latlng: L.LatLng) => void }) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng);
    }
  });
  return null;
}

function useDebounce<T extends (...args: any[]) => any>(callback: T, delay: number) {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  return useCallback((...args: Parameters<T>) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      callback(...args);
    }, delay);
  }, [callback, delay]);
}

// Fix for missing default icon paths in leaflet
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

// Create specific colored icons
const createColoredIcon = (color: string) => {
  return new L.Icon({
    iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${color}.png`,
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
  });
};

const greenIcon = createColoredIcon('green');
const redIcon = createColoredIcon('red');

// Component to dynamically fit map bounds
function MapBoundsFitter({ route, start, end }: { route: [number, number][] | null, start: [number, number] | null, end: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (route && route.length > 0) {
      map.fitBounds(route as L.LatLngBoundsExpression, { padding: [50, 50] });
    } else if (start && end) {
      map.fitBounds([start, end] as L.LatLngBoundsExpression, { padding: [50, 50] });
    } else if (start) {
      map.setView(start as L.LatLngExpression, 14);
    } else if (end) {
      map.setView(end as L.LatLngExpression, 14);
    }
  }, [map, route, start, end]);
  return null;
}

interface AddJourneyModalProps {
  isOpen: boolean;
  onClose: () => void;
  preUploadedVideoId?: string;
  preUploadedFilename?: string;
  preProcessedDuration?: number;
}

export function AddJourneyModal({ isOpen, onClose, preUploadedVideoId, preUploadedFilename, preProcessedDuration }: AddJourneyModalProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Basic Form State
  const [busId, setBusId] = useState('');
  const [busName, setBusName] = useState('');
  const [journeyName, setJourneyName] = useState('');
  const [videoFile, setVideoFile] = useState<File | null>(null);
  
  // Location Search State
  const [startQuery, setStartQuery] = useState('');
  const [startResults, setStartResults] = useState<LocationSearchResult[]>([]);
  const [isSearchingStart, setIsSearchingStart] = useState(false);
  const [selectedStart, setSelectedStart] = useState<LocationSearchResult | null>(null);
  const [isStartDropdownOpen, setIsStartDropdownOpen] = useState(false);

  const [endQuery, setEndQuery] = useState('');
  const [endResults, setEndResults] = useState<LocationSearchResult[]>([]);
  const [isSearchingEnd, setIsSearchingEnd] = useState(false);
  const [selectedEnd, setSelectedEnd] = useState<LocationSearchResult | null>(null);
  const [isEndDropdownOpen, setIsEndDropdownOpen] = useState(false);

  // Routing State
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [isRouting, setIsRouting] = useState(false);
  const [routeError, setRouteError] = useState('');

  // Map Picker State
  const [activePicker, setActivePicker] = useState<'start' | 'end' | null>(null);

  const handleMapClick = async (latlng: L.LatLng, forceTarget?: 'start' | 'end') => {
    let target = forceTarget || activePicker;
    if (!target) {
      if (!selectedStart) target = 'start';
      else if (!selectedEnd) target = 'end';
      else return; 
    }
    
    // Set fallback immediately for UX
    const fallbackResult: LocationSearchResult = {
      place_id: Date.now(),
      display_name: `Loading location...`,
      lat: latlng.lat,
      lon: latlng.lng
    };
    
    if (target === 'start') {
      setSelectedStart(fallbackResult);
      setStartQuery('');
      setIsStartDropdownOpen(false);
    } else {
      setSelectedEnd(fallbackResult);
      setEndQuery('');
      setIsEndDropdownOpen(false);
    }

    // Geocode in background
    const result = await LocationService.reverseGeocode(latlng.lat, latlng.lng);
    
    if (target === 'start') {
      setSelectedStart(result);
      if (!selectedEnd && !activePicker && !forceTarget) setActivePicker('end');
      else setActivePicker(null);
    } else {
      setSelectedEnd(result);
      setActivePicker(null);
    }
  };

  // Overall Submission State
  const [status, setStatus] = useState<'IDLE' | 'UPLOADING' | 'CREATING' | 'QUEUING' | 'SUCCESS' | 'ERROR'>('IDLE');
  const [errorMessage, setErrorMessage] = useState('');

  // Debounced Search Functions
  const debouncedSearchStart = useDebounce(async (q: string) => {
    if (q.length < 3) {
      setStartResults([]);
      return;
    }
    setIsSearchingStart(true);
    const res = await LocationService.search(q);
    setStartResults(res);
    setIsSearchingStart(false);
  }, 1000);

  const debouncedSearchEnd = useDebounce(async (q: string) => {
    if (q.length < 3) {
      setEndResults([]);
      return;
    }
    setIsSearchingEnd(true);
    const res = await LocationService.search(q);
    setEndResults(res);
    setIsSearchingEnd(false);
  }, 1000);

  // Effect to trigger routing when both start and end are selected
  useEffect(() => {
    let active = true;

    async function fetchRoute() {
      if (selectedStart && selectedEnd) {
        setIsRouting(true);
        setRouteError('');
        const res = await LocationService.getRoute(
          { lat: selectedStart.lat, lon: selectedStart.lon },
          { lat: selectedEnd.lat, lon: selectedEnd.lon }
        );
        if (active) {
          if (res) {
            setRoute(res);
          } else {
            setRoute(null);
            setRouteError('Unable to generate a road route. Please try another location.');
          }
          setIsRouting(false);
        }
      } else {
        setRoute(null);
      }
    }

    fetchRoute();
    return () => { active = false; };
  }, [selectedStart, selectedEnd]);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setVideoFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!busId || !busName || !journeyName || (!videoFile && !preUploadedVideoId)) {
      setErrorMessage('Please fill in all basic journey details and select a video.');
      setStatus('ERROR');
      return;
    }
    
    if (!selectedStart) {
      setErrorMessage('Select a starting location.');
      setStatus('ERROR');
      return;
    }

    if (!selectedEnd) {
      setErrorMessage('Select a destination.');
      setStatus('ERROR');
      return;
    }

    if (selectedStart.place_id === selectedEnd.place_id) {
      setErrorMessage('Start location and destination cannot be identical.');
      setStatus('ERROR');
      return;
    }

    if (!route) {
      setErrorMessage('Unable to generate a road route. Please resolve map errors before saving.');
      setStatus('ERROR');
      return;
    }

    try {
      setStatus('UPLOADING');
      setErrorMessage('');

      let videoId = preUploadedVideoId;
      let videoFilename = preUploadedFilename;
      let duration = preProcessedDuration || 0;

      if (!preUploadedVideoId && videoFile) {
        // 1. Upload Video
        const formData = new FormData();
        formData.append('file', videoFile);
        
        const uploadRes = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/video/upload`, {
          method: 'POST',
          body: formData,
        });

        if (!uploadRes.ok) {
          const err = await uploadRes.json();
          throw new Error(err.detail || 'Video upload failed');
        }

        const uploadData = await uploadRes.json();
        videoId = uploadData.video_id;
        videoFilename = uploadData.filename;
        duration = uploadData.metadata?.duration_seconds || 0;
      }

      // RC-2 safety net: if duration is still 0 (race condition or pre-uploaded path),
      // fetch the real duration from the backend metadata endpoint before creating the journey.
      // The backend (RC-1 fix) will also read from disk as a final fallback, but we
      // provide the best value available here to keep the DB consistent.
      if ((!duration || duration <= 0) && videoId) {
        try {
          const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
          const metaRes = await fetch(`${API_BASE}/api/video/${videoId}/metadata`);
          if (metaRes.ok) {
            const metaData = await metaRes.json();
            if (metaData.duration_seconds && metaData.duration_seconds > 0) {
              duration = metaData.duration_seconds;
              console.info('[VIDEO-GPS SYNC] Duration resolved from metadata endpoint: %.3fs video_id=%s', duration, videoId);
            }
          }
        } catch (metaErr) {
          console.warn('[VIDEO-GPS SYNC] Metadata fetch failed, backend will read from disk:', metaErr);
        }
      }

      // 2. Create Journey with Route Points
      setStatus('CREATING');
      
      const routePointsPayload = route.geometry.map(pt => ({
        lat: pt[0],
        lng: pt[1]
      }));

      const journeyRes = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/missions/journey`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          bus_id: busId,
          bus_name: busName,
          journey_name: journeyName,
          video_id: videoId,
          video_filename: videoFilename,
          duration: duration,
          start_location: selectedStart.display_name,
          destination: selectedEnd.display_name,
          route_points: routePointsPayload,
          status: preUploadedVideoId ? 'READY' : 'QUEUED'
        }),
      });

      if (!journeyRes.ok) {
        const err = await journeyRes.json();
        throw new Error(err.detail || 'Journey creation failed');
      }

      const journeyData = await journeyRes.json();
      void journeyData; // journey record stored; video_id already captured above

      // 3. Trigger AI Processing — fire and forget, backend handles the rest (ONLY IF NOT PRE-PROCESSED)
      if (!preUploadedVideoId) {
        setStatus('QUEUING');
        const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        try {
          const processRes = await fetch(`${API_BASE}/api/ai/unified/process/${videoId}`, {
            method: 'POST',
          });
          if (!processRes.ok) {
            // Non-fatal: journey exists, processing can be retried. Just warn.
            console.warn('[Phase9] AI processing trigger returned non-OK:', processRes.status);
          } else {
            const pd = await processRes.json();
            console.info('[Phase9] AI job queued job_id=%s video_id=%s', pd.job_id, videoId);
          }
        } catch (processErr) {
          // Network error triggering AI — journey is still saved, log and continue
          console.warn('[Phase9] AI processing trigger failed (journey saved):', processErr);
        }
      }

      setStatus('SUCCESS');
      
      // Refresh fleet data
      queryClient.invalidateQueries({ queryKey: ['fleet'] });
      
      setTimeout(() => {
        handleClose();
      }, 2000);
      
    } catch (error: any) {
      setStatus('ERROR');
      setErrorMessage(error.message || 'An unexpected error occurred');
    }
  };

  const handleClose = () => {
    setBusId('');
    setBusName('');
    setJourneyName('');
    setVideoFile(null);
    setStartQuery('');
    setEndQuery('');
    setSelectedStart(null);
    setSelectedEnd(null);
    setStartResults([]);
    setEndResults([]);
    setRoute(null);
    setRouteError('');
    setStatus('IDLE');
    setErrorMessage('');
    onClose();
  };

  const formatSize = (bytes: number) => {
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="fixed inset-0 z-50 bg-background/90 backdrop-blur-sm flex items-center justify-center p-4 md:p-8">
      <div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-6xl h-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border/50 shrink-0">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Video className="w-5 h-5 text-primary" />
            Add Bus Journey
          </h2>
          <button onClick={handleClose} className="p-1.5 hover:bg-muted rounded-md transition-colors" disabled={status === 'UPLOADING' || status === 'CREATING'}>
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Content Split */}
        <div className="flex flex-1 overflow-hidden">
          
          {/* Left Side: Form */}
          <div className="w-full md:w-1/2 p-6 overflow-y-auto border-r border-border/50 flex flex-col gap-6">
            
            {/* Step 1: Basic Info */}
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider border-b border-border/50 pb-2">1. Journey Details</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground uppercase">Bus ID</label>
                  <input 
                    type="text" 
                    value={busId}
                    onChange={e => setBusId(e.target.value)}
                    placeholder="e.g. UW-101"
                    className="w-full bg-background text-foreground border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
                    disabled={status !== 'IDLE' && status !== 'ERROR'}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground uppercase">Bus Name</label>
                  <input 
                    type="text" 
                    value={busName}
                    onChange={e => setBusName(e.target.value)}
                    placeholder="e.g. Urban Watch 101"
                    className="w-full bg-background text-foreground border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
                    disabled={status !== 'IDLE' && status !== 'ERROR'}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground uppercase">Journey Name</label>
                <input 
                  type="text" 
                  value={journeyName}
                  onChange={e => setJourneyName(e.target.value)}
                  placeholder="e.g. Jaipur Urban Survey A"
                  className="w-full bg-background text-foreground border border-input rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
                  disabled={status !== 'IDLE' && status !== 'ERROR'}
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground uppercase">Survey Video</label>
                {preUploadedVideoId ? (
                  <div className="border border-border rounded-lg p-3 bg-secondary/20 flex items-center justify-between">
                    <div className="flex items-center gap-3 overflow-hidden">
                      <FileVideo className="w-5 h-5 text-primary shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate" title={preUploadedFilename || 'Pre-uploaded video'}>{preUploadedFilename || 'Analyzed Video Attached'}</p>
                        <p className="text-xs text-muted-foreground">Analysis Complete</p>
                      </div>
                    </div>
                  </div>
                ) : !videoFile ? (
                  <div 
                    onClick={() => status === 'IDLE' || status === 'ERROR' ? fileInputRef.current?.click() : null}
                    className={`border-2 border-dashed border-border rounded-lg p-4 flex items-center justify-center gap-3 transition-colors ${status === 'IDLE' || status === 'ERROR' ? 'hover:bg-muted/30 hover:border-primary/50 cursor-pointer' : 'opacity-50 cursor-not-allowed'}`}
                  >
                    <Upload className="w-5 h-5 text-muted-foreground" />
                    <span className="text-sm font-medium">Click to select MP4 video</span>
                    <input 
                      ref={fileInputRef}
                      type="file" 
                      accept="video/*"
                      className="hidden" 
                      onChange={handleFileChange}
                    />
                  </div>
                ) : (
                  <div className="border border-border rounded-lg p-3 bg-secondary/20 flex items-center justify-between">
                    <div className="flex items-center gap-3 overflow-hidden">
                      <FileVideo className="w-5 h-5 text-primary shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate" title={videoFile.name}>{videoFile.name}</p>
                        <p className="text-xs text-muted-foreground">{formatSize(videoFile.size)}</p>
                      </div>
                    </div>
                    {(status === 'IDLE' || status === 'ERROR') && (
                      <button onClick={() => setVideoFile(null)} className="p-1 text-muted-foreground hover:bg-muted rounded">
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Step 2: Route Selection */}
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider border-b border-border/50 pb-2 flex items-center justify-between">
                <span>2. Route Assignment</span>
                <span className="text-[10px] font-normal bg-secondary px-2 py-0.5 rounded text-muted-foreground">Synthesizes demo route</span>
              </h3>
              
              {/* Start Location Search */}
              <div className="space-y-2 relative">
                <label className="text-xs font-medium text-green-500 uppercase flex items-center justify-between">
                  <div className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> Start Location</div>
                  <button 
                    type="button" 
                    onClick={() => setActivePicker(activePicker === 'start' ? null : 'start')}
                    className={`text-[10px] px-2 py-0.5 rounded transition-colors border ${activePicker === 'start' ? 'bg-green-500/20 text-green-500 border-green-500/30' : 'bg-transparent text-muted-foreground border-border hover:bg-muted'}`}
                  >
                    {activePicker === 'start' ? 'CLICK ON MAP...' : 'PICK ON MAP'}
                  </button>
                </label>
                {selectedStart ? (
                  <div className="flex items-center justify-between bg-green-500/10 border border-green-500/20 p-3 rounded-md">
                    <span className="text-sm font-medium text-green-600 dark:text-green-400 truncate pr-2">{selectedStart.display_name}</span>
                    <button onClick={() => setSelectedStart(null)} className="shrink-0 p-1 hover:bg-green-500/20 rounded text-green-600 dark:text-green-400">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <input 
                      type="text" 
                      value={startQuery}
                      onChange={(e) => {
                        setStartQuery(e.target.value);
                        setIsStartDropdownOpen(true);
                        debouncedSearchStart(e.target.value);
                      }}
                      onFocus={() => setIsStartDropdownOpen(true)}
                      placeholder="Search a location... (e.g. Tonk Road, Jaipur)"
                      className="w-full bg-background text-foreground border border-input rounded-md pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
                    />
                    {isSearchingStart && <Loader2 className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground animate-spin" />}
                    
                    {/* Search Dropdown */}
                    {isStartDropdownOpen && startQuery.length >= 3 && (
                      <div className="absolute top-full left-0 right-0 mt-1 bg-card border border-border rounded-md shadow-xl z-10 max-h-60 overflow-y-auto">
                        {!isSearchingStart && startResults.length === 0 ? (
                          <div className="p-3 text-sm text-muted-foreground italic text-center">No locations found.</div>
                        ) : (
                          startResults.map(res => (
                            <div 
                              key={res.place_id} 
                              onClick={() => {
                                setSelectedStart(res);
                                setStartQuery('');
                                setIsStartDropdownOpen(false);
                              }}
                              className="p-3 hover:bg-muted cursor-pointer border-b border-border/50 last:border-0"
                            >
                              <div className="text-sm font-medium truncate">{res.display_name.split(',')[0]}</div>
                              <div className="text-xs text-muted-foreground truncate">{res.display_name}</div>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* End Location Search */}
              <div className="space-y-2 relative">
                <label className="text-xs font-medium text-red-500 uppercase flex items-center justify-between">
                  <div className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> Destination</div>
                  <button 
                    type="button" 
                    onClick={() => setActivePicker(activePicker === 'end' ? null : 'end')}
                    className={`text-[10px] px-2 py-0.5 rounded transition-colors border ${activePicker === 'end' ? 'bg-red-500/20 text-red-500 border-red-500/30' : 'bg-transparent text-muted-foreground border-border hover:bg-muted'}`}
                  >
                    {activePicker === 'end' ? 'CLICK ON MAP...' : 'PICK ON MAP'}
                  </button>
                </label>
                {selectedEnd ? (
                  <div className="flex items-center justify-between bg-red-500/10 border border-red-500/20 p-3 rounded-md">
                    <span className="text-sm font-medium text-red-600 dark:text-red-400 truncate pr-2">{selectedEnd.display_name}</span>
                    <button onClick={() => setSelectedEnd(null)} className="shrink-0 p-1 hover:bg-red-500/20 rounded text-red-600 dark:text-red-400">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <input 
                      type="text" 
                      value={endQuery}
                      onChange={(e) => {
                        setEndQuery(e.target.value);
                        setIsEndDropdownOpen(true);
                        debouncedSearchEnd(e.target.value);
                      }}
                      onFocus={() => setIsEndDropdownOpen(true)}
                      placeholder="Search destination... (e.g. Jaipur Railway Station)"
                      className="w-full bg-background text-foreground border border-input rounded-md pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
                    />
                    {isSearchingEnd && <Loader2 className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground animate-spin" />}
                    
                    {/* Search Dropdown */}
                    {isEndDropdownOpen && endQuery.length >= 3 && (
                      <div className="absolute top-full left-0 right-0 mt-1 bg-card border border-border rounded-md shadow-xl z-10 max-h-60 overflow-y-auto">
                        {!isSearchingEnd && endResults.length === 0 ? (
                          <div className="p-3 text-sm text-muted-foreground italic text-center">No locations found.</div>
                        ) : (
                          endResults.map(res => (
                            <div 
                              key={res.place_id} 
                              onClick={() => {
                                setSelectedEnd(res);
                                setEndQuery('');
                                setIsEndDropdownOpen(false);
                              }}
                              className="p-3 hover:bg-muted cursor-pointer border-b border-border/50 last:border-0"
                            >
                              <div className="text-sm font-medium truncate">{res.display_name.split(',')[0]}</div>
                              <div className="text-xs text-muted-foreground truncate">{res.display_name}</div>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Routing Preview Data */}
              {isRouting && (
                <div className="p-4 flex items-center justify-center gap-3 text-sm text-muted-foreground bg-secondary/30 rounded-lg animate-pulse border border-border/50">
                  <Navigation className="w-4 h-4 animate-spin" /> Generating Road Route...
                </div>
              )}
              {routeError && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-md flex items-start gap-2 text-red-500 text-sm">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  <p>{routeError}</p>
                </div>
              )}
              {route && !isRouting && (
                <div className="p-4 bg-primary/5 border border-primary/20 rounded-lg flex flex-col gap-2 relative overflow-hidden">
                  <div className="absolute -right-4 -top-4 text-primary/10">
                    <Navigation className="w-24 h-24" />
                  </div>
                  <h4 className="text-xs font-bold uppercase tracking-widest text-primary/80">Route Preview</h4>
                  <div className="flex gap-6">
                    <div>
                      <div className="text-2xl font-black text-foreground">{route.distance_km.toFixed(1)} <span className="text-sm font-medium text-muted-foreground">km</span></div>
                      <div className="text-xs text-muted-foreground">Distance</div>
                    </div>
                    <div>
                      <div className="text-2xl font-black text-foreground">{Math.round(route.duration_min)} <span className="text-sm font-medium text-muted-foreground">min</span></div>
                      <div className="text-xs text-muted-foreground">Estimated Travel</div>
                    </div>
                  </div>
                </div>
              )}

            </div>

            {/* Error / Success messages */}
            {status === 'ERROR' && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-md flex items-start gap-2 text-red-500 text-sm mt-auto">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <p>{errorMessage}</p>
              </div>
            )}

            {status === 'SUCCESS' && (
              <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-md flex items-center gap-2 text-green-500 text-sm mt-auto">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <p>Journey created! AI processing has been queued — check Fleet page for status.</p>
              </div>
            )}

          </div>

          {/* Right Side: Map Preview */}
          <div className={`hidden md:block md:w-1/2 bg-muted relative border-l border-border/50 ${activePicker ? 'cursor-crosshair' : ''}`}>
            <MapContainer 
              center={[26.9124, 75.7873]} 
              zoom={12} 
              className="w-full h-full"
              zoomControl={true}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                maxZoom={19}
              />
              <MapClickEvents onMapClick={handleMapClick} />
              
              {selectedStart && (
                <Marker 
                  position={[selectedStart.lat, selectedStart.lon]} 
                  icon={greenIcon}
                  draggable={true}
                  eventHandlers={{
                    dragend: (e) => {
                      const marker = e.target;
                      const position = marker.getLatLng();
                      handleMapClick(position, 'start');
                    }
                  }}
                />
              )}
              {selectedEnd && (
                <Marker 
                  position={[selectedEnd.lat, selectedEnd.lon]} 
                  icon={redIcon} 
                  draggable={true}
                  eventHandlers={{
                    dragend: (e) => {
                      const marker = e.target;
                      const position = marker.getLatLng();
                      handleMapClick(position, 'end');
                    }
                  }}
                />
              )}
              {route && (
                <Polyline 
                  positions={route.geometry} 
                  pathOptions={{ color: '#3b82f6', weight: 4, opacity: 0.8 }} 
                />
              )}
              
              <MapBoundsFitter 
                route={route?.geometry || null} 
                start={selectedStart ? [selectedStart.lat, selectedStart.lon] : null} 
                end={selectedEnd ? [selectedEnd.lat, selectedEnd.lon] : null} 
              />
            </MapContainer>
            
            {(!selectedStart || !selectedEnd) && (
              <div className="absolute top-4 right-14 z-[400] pointer-events-none">
                <div className="bg-card px-3 py-1.5 rounded-md border border-border shadow-md text-xs font-semibold text-muted-foreground">
                  Select start & destination
                </div>
              </div>
            )}
            
            {/* Attribution overlay */}
            <div className="absolute bottom-1 right-1 z-[400] text-[10px] bg-background/70 px-2 py-0.5 rounded pointer-events-none text-muted-foreground">
              Search by Nominatim | Routing by OSRM
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-border/50 bg-secondary/30 shrink-0 flex justify-end gap-3">
          <button 
            type="button" 
            onClick={handleClose}
            className="px-6 py-2 text-sm font-medium hover:bg-muted rounded-md transition-colors"
            disabled={status === 'UPLOADING' || status === 'CREATING' || status === 'QUEUING'}
          >
            Cancel
          </button>
          <button 
            type="submit"
            onClick={handleSubmit}
            disabled={status !== 'IDLE' && status !== 'ERROR'}
            className="px-6 py-2 bg-primary text-primary-foreground text-sm font-bold rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {status === 'UPLOADING' ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Uploading Video...</>
            ) : status === 'CREATING' ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Saving Route & Journey...</>
            ) : status === 'QUEUING' ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Queuing AI Processing...</>
            ) : (
              'SAVE ROUTE & JOURNEY'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
