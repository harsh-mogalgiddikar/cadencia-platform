import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FormFieldProps {
  label: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
  hint?: string;
}

export function FormField({ label, error, required, children, hint }: FormFieldProps) {
  return (
    <div className="space-y-1.5 w-full">
      <div className="flex justify-between items-baseline">
        <label className="text-sm font-medium text-foreground">
          {label}
          {required && <span className="text-destructive ml-1">*</span>}
        </label>
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      <div className={cn('relative w-full rounded-md', error && 'ring-1 ring-destructive')}>
        {children}
      </div>
      {error && (
        <div className="flex items-center gap-1 text-xs text-destructive mt-1">
          <AlertCircle className="h-3 w-3 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
