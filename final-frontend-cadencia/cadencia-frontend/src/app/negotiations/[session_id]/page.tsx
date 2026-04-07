import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { MessageSquare } from 'lucide-react';

export default function NegotiationRoomPage() {
  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Negotiation Room</h1>
        <p className="text-sm text-muted-foreground mt-1">Live AI negotiation session</p>
        <div className="mt-8">
          <EmptyState
            icon={MessageSquare}
            title="Negotiation Room coming soon"
            description="Live AI negotiation session will appear here"
          />
        </div>
      </div>
    </AppShell>
  );
}
