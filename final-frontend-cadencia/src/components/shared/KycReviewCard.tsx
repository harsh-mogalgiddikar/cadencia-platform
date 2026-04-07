import * as React from 'react';
import { Button } from '@/components/ui/button';
import { StatusBadge } from './StatusBadge';
import { ConfirmDialog } from './ConfirmDialog';
import { formatDate } from '@/lib/utils';

export interface AdminEnterprise {
  id: string;
  legal_name: string;
  kyc_status: string;
  trade_role: string;
  user_count: number;
  created_at: string;
}

interface KycReviewCardProps {
  enterprise: AdminEnterprise;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  isLoading: boolean;
}

export function KycReviewCard({ enterprise, onApprove, onReject, isLoading }: KycReviewCardProps) {
  const [action, setAction] = React.useState<'approve' | 'reject' | null>(null);

  const handleConfirm = () => {
    if (action === 'approve') onApprove(enterprise.id);
    if (action === 'reject') onReject(enterprise.id);
    setAction(null);
  };

  return (
    <>
      <div className="bg-card border border-border border-l-4 border-l-amber-500 rounded-lg p-4 mb-4 last:mb-0">
        <div className="flex justify-between items-start mb-2">
          <h4 className="font-semibold text-foreground">{enterprise.legal_name}</h4>
          <StatusBadge status={enterprise.kyc_status} size="sm" />
        </div>
        <p className="text-xs text-muted-foreground mb-1">
          {enterprise.id} &bull; <span className="capitalize">{enterprise.trade_role.toLowerCase()}</span> &bull; {enterprise.user_count} users
        </p>
        <p className="text-xs text-muted-foreground mb-4">
          Documents received {formatDate(enterprise.created_at)}
        </p>
        <div className="flex gap-2">
          <Button 
            size="sm" 
            className="bg-primary text-primary-foreground text-xs px-3 py-1.5 h-auto leading-none w-full"
            onClick={() => setAction('approve')}
            disabled={isLoading}
          >
            Approve KYC
          </Button>
          <Button 
            size="sm" 
            variant="outline" 
            className="border-destructive text-destructive hover:bg-destructive/10 text-xs px-3 py-1.5 h-auto leading-none w-full"
            onClick={() => setAction('reject')}
            disabled={isLoading}
          >
            Reject KYC
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={!!action}
        onOpenChange={(v) => !v && setAction(null)}
        title={action === 'approve' ? 'Approve KYC' : 'Reject KYC'}
        description={
          action === 'approve' 
            ? `Are you sure you want to approve KYC for ${enterprise.legal_name}? This will allow them to trade on the platform.`
            : `Are you sure you want to reject KYC for ${enterprise.legal_name}? They will need to submit new documents.`
        }
        confirmLabel={action === 'approve' ? 'Approve' : 'Reject'}
        variant={action === 'reject' ? 'destructive' : 'default'}
        onConfirm={handleConfirm}
        isLoading={isLoading}
      />
    </>
  );
}
