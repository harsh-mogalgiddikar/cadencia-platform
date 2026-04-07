import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { Handshake } from 'lucide-react';

export default function NegotiationsPage() {
  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Negotiations</h1>
        <p className="text-sm text-muted-foreground mt-1">Active and historical negotiation sessions</p>
        <div className="mt-8">
          <EmptyState
            icon={Handshake}
            title="Negotiations coming soon"
            description="Active and historical negotiation sessions will appear here"
          />
        </div>
      </div>
    </AppShell>
  );
}
