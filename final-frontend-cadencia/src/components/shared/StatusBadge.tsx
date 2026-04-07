import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

const statusConfig: Record<string, { label: string; className: string }> = {
  // Trade roles
  BUYER:         { label: 'Buyer',         className: 'bg-green-950 text-green-400 border-green-900' },
  SELLER:        { label: 'Seller',        className: 'bg-blue-950 text-blue-400 border-blue-900' },
  BOTH:          { label: 'Buyer & Seller', className: 'bg-secondary text-secondary-foreground border-border' },

  // Green — success states
  ACTIVE:        { label: 'Active',        className: 'bg-green-950 text-green-400 border-green-900' },
  AGREED:        { label: 'Agreed',        className: 'bg-green-950 text-green-400 border-green-900' },
  MATCHED:       { label: 'Matched',       className: 'bg-green-950 text-green-400 border-green-900' },
  RELEASED:      { label: 'Released',      className: 'bg-green-950 text-green-400 border-green-900' },
  KYCD:          { label: 'KYC Active',    className: 'bg-green-950 text-green-400 border-green-900' },

  // Amber — in-progress states
  PENDING:       { label: 'Pending',       className: 'bg-amber-950 text-amber-400 border-amber-900' },
  PARSED:        { label: 'Parsed',        className: 'bg-amber-950 text-amber-400 border-amber-900' },
  DEPLOYED:      { label: 'Deployed',      className: 'bg-amber-950 text-amber-400 border-amber-900' },
  STALLED:       { label: 'Stalled',       className: 'bg-amber-950 text-amber-400 border-amber-900' },

  // Blue — confirmed states
  CONFIRMED:     { label: 'Confirmed',     className: 'bg-blue-950 text-blue-400 border-blue-900' },
  FUNDED:        { label: 'Funded',        className: 'bg-blue-950 text-blue-400 border-blue-900' },
  WALLET_LINKED: { label: 'Wallet Linked', className: 'bg-blue-950 text-blue-400 border-blue-900' },
  ADMIN:         { label: 'Admin',         className: 'bg-blue-950 text-blue-400 border-blue-900' },

  // Muted — neutral / initial states
  DRAFT:         { label: 'Draft',         className: 'bg-muted text-muted-foreground border-border' },
  NOT_SUBMITTED: { label: 'Not Submitted', className: 'bg-muted text-muted-foreground border-border' },
  IDLE:          { label: 'Idle',          className: 'bg-muted text-muted-foreground border-border' },
  TERMINATED:    { label: 'Terminated',    className: 'bg-muted text-muted-foreground border-border' },

  // Red — error / failure states
  FAILED:        { label: 'Failed',        className: 'bg-red-950 text-destructive border-red-900' },
  REJECTED:      { label: 'Rejected',      className: 'bg-red-950 text-destructive border-red-900' },
  FROZEN:        { label: 'Frozen',        className: 'bg-red-950 text-destructive border-red-900' },
  REFUNDED:      { label: 'Refunded',      className: 'bg-red-950 text-destructive border-red-900' },
};

export function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const config = statusConfig[status] ?? {
    label: status,
    className: 'bg-muted text-muted-foreground border-border',
  };

  return (
    <span className={cn(
      'inline-flex items-center border font-medium rounded-md',
      size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
      config.className
    )}>
      {config.label}
    </span>
  );
}
