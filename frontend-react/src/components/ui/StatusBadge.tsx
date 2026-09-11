import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: string;
  type?: 'severity' | 'state' | 'connectivity';
  className?: string;
}

export function StatusBadge({ status, type = 'severity', className }: StatusBadgeProps) {
  const s = status.toUpperCase();
  
  let colors = 'bg-secondary text-secondary-foreground';

  if (type === 'severity') {
    switch (s) {
      case 'CRITICAL': colors = 'bg-red-500/20 text-red-500 border border-red-500/30'; break;
      case 'HIGH': colors = 'bg-orange-500/20 text-orange-500 border border-orange-500/30'; break;
      case 'MEDIUM': colors = 'bg-yellow-500/20 text-yellow-500 border border-yellow-500/30'; break;
      case 'LOW': colors = 'bg-blue-500/20 text-blue-500 border border-blue-500/30'; break;
    }
  } else if (type === 'connectivity') {
    switch (s) {
      case 'LIVE':
      case 'ONLINE': colors = 'bg-emerald-500/20 text-emerald-500 border border-emerald-500/30'; break;
      case 'WARNING':
      case 'STALE': colors = 'bg-orange-500/20 text-orange-500 border border-orange-500/30'; break;
      case 'OFFLINE':
      case 'ERROR': colors = 'bg-red-500/20 text-red-500 border border-red-500/30'; break;
    }
  } else if (type === 'state') {
    switch (s) {
      case 'OPEN':
      case 'ACTIVE': colors = 'bg-blue-500/20 text-blue-500 border border-blue-500/30'; break;
      case 'INVESTIGATING':
      case 'IN_PROGRESS':
      case 'ASSIGNED': colors = 'bg-orange-500/20 text-orange-500 border border-orange-500/30'; break;
      case 'RESOLVED':
      case 'CONFIRMED':
      case 'COMPLETE': colors = 'bg-emerald-500/20 text-emerald-500 border border-emerald-500/30'; break;
      case 'DISMISSED':
      case 'SUPPRESSED':
      case 'REJECTED': colors = 'bg-secondary/50 text-muted-foreground border border-border'; break;
    }
  }

  return (
    <span className={cn("px-2.5 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase inline-flex items-center justify-center whitespace-nowrap", colors, className)}>
      {s}
    </span>
  );
}
