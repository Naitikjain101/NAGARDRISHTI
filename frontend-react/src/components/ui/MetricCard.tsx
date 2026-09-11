import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  description?: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  className?: string;
}

export function MetricCard({ title, value, icon: Icon, description, trend, className }: MetricCardProps) {
  return (
    <div className={cn("bg-card border border-border rounded-lg p-6 flex flex-col", className)}>
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-muted-foreground text-sm font-medium">{title}</h3>
        <div className="p-2 bg-secondary rounded-lg">
          <Icon className="h-4 w-4 text-primary" />
        </div>
      </div>
      
      <div className="flex items-baseline gap-2">
        <h2 className="text-3xl font-bold">{value}</h2>
        {trend && (
          <span className={cn(
            "text-sm font-medium",
            trend.isPositive ? "text-emerald-500" : "text-destructive"
          )}>
            {trend.isPositive ? '+' : '-'}{Math.abs(trend.value)}%
          </span>
        )}
      </div>
      
      {description && (
        <p className="text-xs text-muted-foreground mt-2">{description}</p>
      )}
    </div>
  );
}
