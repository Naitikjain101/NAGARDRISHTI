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
      case 'CRITICAL': colors = 'bg-red-100 text-red-800 border-red-200 dark:bg-red-500/20 dark:text-red-400 dark:border-red-500/30'; break;
      case 'HIGH': colors = 'bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-500/20 dark:text-orange-400 dark:border-orange-500/30'; break;
      case 'MEDIUM': colors = 'bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-500/20 dark:text-yellow-400 dark:border-yellow-500/30'; break;
      case 'LOW': colors = 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-500/20 dark:text-blue-400 dark:border-blue-500/30'; break;
    }
  } else if (type === 'connectivity') {
    switch (s) {
      case 'LIVE':
      case 'ONLINE': colors = 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-500/20 dark:text-emerald-400 dark:border-emerald-500/30'; break;
      case 'WARNING':
      case 'STALE': colors = 'bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-500/20 dark:text-orange-400 dark:border-orange-500/30'; break;
      case 'OFFLINE':
      case 'ERROR': colors = 'bg-red-100 text-red-800 border-red-200 dark:bg-red-500/20 dark:text-red-400 dark:border-red-500/30'; break;
    }
  } else if (type === 'state') {
    switch (s) {
      case 'OPEN':
      case 'ACTIVE': colors = 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-500/20 dark:text-blue-400 dark:border-blue-500/30'; break;
      case 'PENDING':
      case 'INVESTIGATING':
      case 'IN_PROGRESS':
      case 'ASSIGNED': colors = 'bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-500/20 dark:text-orange-400 dark:border-orange-500/30'; break;
      case 'RESOLVED':
      case 'CONFIRMED':
      case 'COMPLETE': colors = 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-500/20 dark:text-emerald-400 dark:border-emerald-500/30'; break;
      case 'DISMISSED':
      case 'SUPPRESSED':
      case 'REJECTED': colors = 'bg-zinc-100 text-zinc-700 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:border-zinc-700'; break;
    }
  }

  return (
    <span className={cn("px-2.5 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase inline-flex items-center justify-center whitespace-nowrap", colors, className)}>
      {s}
    </span>
  );
}
