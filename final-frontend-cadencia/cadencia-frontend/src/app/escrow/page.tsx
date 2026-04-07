import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { Landmark } from 'lucide-react';

export default function EscrowPage() {
  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Escrow</h1>
        <p className="text-sm text-muted-foreground mt-1">Algorand smart contract escrow management</p>
        <div className="mt-8">
          <EmptyState
            icon={Landmark}
            title="Escrow coming soon"
            description="Algorand smart contract escrow management will appear here"
          />
        </div>
      </div>
    </AppShell>
  );
}
