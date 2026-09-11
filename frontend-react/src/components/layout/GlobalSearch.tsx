import { useState, useEffect } from 'react';
import { Search, MapPin, AlertTriangle } from 'lucide-react';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { useNavigate } from 'react-router-dom';

export function GlobalSearch({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
  const [query, setQuery] = useState('');
  const { data } = useRealtimeIncidents();
  const navigate = useNavigate();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (isOpen) onClose();
        else onClose(); // this is a controlled component, we should pass toggle instead of open/close logic here
      }
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const incidents = data?.incidents || [];
  
  const results = query.length > 0 ? incidents.filter(i => 
    i.id.toLowerCase().includes(query.toLowerCase()) || 
    i.type.toLowerCase().includes(query.toLowerCase()) ||
    i.status.toLowerCase().includes(query.toLowerCase())
  ).slice(0, 5) : [];

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-background/80 backdrop-blur-sm" onClick={onClose}>
      <div 
        className="w-full max-w-lg bg-card border border-border rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center px-4 py-3 border-b border-border">
          <Search className="h-5 w-5 text-muted-foreground mr-3" />
          <input
            autoFocus
            type="text"
            className="flex-1 bg-transparent border-none outline-none text-foreground text-sm placeholder:text-muted-foreground"
            placeholder="Search incidents, buses, or roads..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <kbd className="hidden sm:inline-block pointer-events-none bg-muted text-muted-foreground text-[10px] font-mono px-1.5 py-0.5 rounded border border-border font-semibold">
            ESC
          </kbd>
        </div>
        
        {query.length > 0 && (
          <div className="max-h-[300px] overflow-y-auto py-2">
            {results.length > 0 ? (
              <div className="px-2">
                <div className="text-xs font-semibold text-muted-foreground px-2 py-1.5 uppercase tracking-wider">
                  Incidents
                </div>
                {results.map(incident => (
                  <button 
                    key={incident.id}
                    className="w-full text-left px-2 py-2 flex items-start gap-3 rounded-md hover:bg-secondary transition-colors"
                    onClick={() => {
                      onClose();
                      navigate('/incidents'); // In a real app we might deep link
                    }}
                  >
                    <div className="mt-0.5 p-1.5 bg-secondary rounded text-primary">
                       {incident.type === 'waterlogging' ? <AlertTriangle className="h-4 w-4" /> : <MapPin className="h-4 w-4" />}
                    </div>
                    <div>
                      <p className="text-sm font-medium capitalize">{incident.type.replace('_', ' ')} Incident</p>
                      <p className="text-xs text-muted-foreground font-mono">ID: {incident.id.slice(0,8)} • {incident.status}</p>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                No results found for "{query}".
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
