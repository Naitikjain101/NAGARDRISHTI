import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  description?: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  variant?: 'default' | 'critical' | 'warning' | 'success';
  className?: string;
}

const variantIcon: Record<string, string> = {
  default:  'bg-secondary text-muted-foreground',
  critical: 'bg-red-50 text-red-600',
  warning:  'bg-amber-50 text-amber-600',
  success:  'bg-green-50 text-green-600',
};

export function MetricCard({ title, value, icon: Icon, description, trend, variant = 'default', className }: MetricCardProps) {
  return (
    <div className={cn('bg-card border border-border rounded-lg p-4 shadow-card', className)}>
      <div className="flex items-start justify-between mb-3">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider leading-tight">{title}</p>
        <div className={cn('p-1.5 rounded-md', variantIcon[variant])}>
          <Icon className="h-4 w-4" />
        </div>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-foreground tabular-nums">{value}</span>
        {trend && (
          <span className={cn(
            'text-xs font-semibold',
            trend.isPositive ? 'text-green-600' : 'text-red-600'
          )}>
            {trend.isPositive ? '+' : '-'}{Math.abs(trend.value)}%
          </span>
        )}
      </div>

      {description && (
        <p className="text-xs text-muted-foreground mt-1.5 leading-snug">{description}</p>
      )}
    </div>
  );
}
