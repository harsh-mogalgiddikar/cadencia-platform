'use client';

import { Calendar, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DateRangePickerProps {
  value: string;
  onChange: (value: string) => void;
}

const PRESETS = [
  { value: 'all', label: 'All Time' },
  { value: 'this-week', label: 'This Week' },
  { value: 'this-month', label: 'This Month' },
  { value: 'last-30', label: 'Last 30 Days' },
];

export function DateRangePicker({ value, onChange }: DateRangePickerProps) {
  return (
    <div className="relative">
      <div className="flex items-center gap-2">
        <Calendar className="h-4 w-4 text-muted-foreground shrink-0" />
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            'appearance-none bg-muted border border-border rounded-md px-3 py-1.5 pr-8 text-sm text-foreground',
            'focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer'
          )}
        >
          {PRESETS.map(p => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>
        <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
      </div>
    </div>
  );
}
