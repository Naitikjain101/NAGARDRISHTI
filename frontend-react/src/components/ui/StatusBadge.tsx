import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: string;
  type?: 'severity' | 'state' | 'connectivity';
  className?: string;
}

export function StatusBadge({ status, type = 'severity', className }: StatusBadgeProps) {
  const s = status.toUpperCase();
  
  let colors = 'bg-secondary text-secondary-foreground border-border';

  if (type === 'severity') {
    switch (s) {
      case 'CRITICAL': colors = 'bg-red-100 text-red-700 border-red-200'; break;
      case 'HIGH':     colors = 'bg-orange-100 text-orange-700 border-orange-200'; break;
      case 'MEDIUM':   colors = 'bg-amber-100 text-amber-700 border-amber-200'; break;
      case 'LOW':      colors = 'bg-blue-100 text-blue-700 border-blue-200'; break;
    }
  } else if (type === 'connectivity') {
    switch (s) {
      case 'LIVE':
      case 'ONLINE':      colors = 'bg-green-100 text-green-700 border-green-200'; break;
      case 'CONNECTING':
      case 'WARNING':
      case 'STALE':       colors = 'bg-amber-100 text-amber-700 border-amber-200'; break;
      case 'OFFLINE':
      case 'ERROR':       colors = 'bg-red-100 text-red-700 border-red-200'; break;
    }
  } else if (type === 'state') {
    switch (s) {
      case 'OPEN':
      case 'ACTIVE':        colors = 'bg-blue-100 text-blue-700 border-blue-200'; break;
      case 'UNASSIGNED':    colors = 'bg-orange-100 text-orange-700 border-orange-200'; break;
      case 'PENDING':
      case 'INVESTIGATING':
      case 'IN_PROGRESS':
      case 'ASSIGNED':      colors = 'bg-amber-100 text-amber-700 border-amber-200'; break;
      case 'RESOLVED':
      case 'CONFIRMED':
      case 'COMPLETE':      colors = 'bg-green-100 text-green-700 border-green-200'; break;
      case 'DISMISSED':
      case 'SUPPRESSED':
      case 'REJECTED':      colors = 'bg-gray-100 text-gray-600 border-gray-200'; break;
    }
  }

  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase border whitespace-nowrap',
      colors,
      className
    )}>
      {s}
    </span>
  );
}
