'use client';

import { cn } from '@/lib/utils';

interface FilterChipsProps {
  options: Array<{ value: string; label: string; count?: number }>;
  selected: string;
  onChange: (selected: string) => void;
}

export function FilterChips({ options, selected, onChange }: FilterChipsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(opt => {
        const isActive = selected === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={cn(
              'inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition-colors',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-accent'
            )}
          >
            {opt.label}
            {opt.count != null && (
              <span className={cn(
                'rounded-full px-1.5 py-0.5 text-xs',
                isActive ? 'bg-primary-foreground/20 text-primary-foreground' : 'bg-muted-foreground/20 text-muted-foreground'
              )}>
                {opt.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
