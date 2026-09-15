import { cn } from '@/lib/utils';

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  className?: string;
}

export function Select({ label, className, children, ...props }: SelectProps) {
  return (
    <div className={cn('relative', className)}>
      {label && (
        <label className="block text-xs font-medium text-muted-foreground mb-1">{label}</label>
      )}
      <select
        className={cn(
          'h-8 rounded border border-input bg-card px-2.5 pr-7 text-sm text-foreground',
          'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1',
          'appearance-none cursor-pointer',
          'bg-[url(\'data:image/svg+xml;charset=utf-8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="%236B7684" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>\')] bg-no-repeat bg-[right_0.4rem_center] bg-[length:14px]'
        )}
        {...props}
      >
        {children}
      </select>
    </div>
  );
}
