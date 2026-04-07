import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { Store } from 'lucide-react';

export default function SellerProfilePage() {
  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Seller Profile</h1>
        <p className="text-sm text-muted-foreground mt-1">Your capability profile for AI matching</p>
        <div className="mt-8">
          <EmptyState
            icon={Store}
            title="Seller Profile coming soon"
            description="Your capability profile for AI matching will appear here"
          />
        </div>
      </div>
    </AppShell>
  );
}
