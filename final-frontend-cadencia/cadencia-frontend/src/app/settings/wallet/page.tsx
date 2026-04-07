import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { Wallet } from 'lucide-react';

export default function WalletPage() {
  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Wallet Management</h1>
        <p className="text-sm text-muted-foreground mt-1">Algorand wallet linking and balance</p>
        <div className="mt-8">
          <EmptyState
            icon={Wallet}
            title="Wallet Management coming soon"
            description="Algorand wallet linking and balance will appear here"
          />
        </div>
      </div>
    </AppShell>
  );
}
