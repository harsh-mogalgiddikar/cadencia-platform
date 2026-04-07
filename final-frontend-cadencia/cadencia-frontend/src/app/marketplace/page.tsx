import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { ShoppingCart } from 'lucide-react';

export default function MarketplacePage() {
  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Marketplace</h1>
        <p className="text-sm text-muted-foreground mt-1">Request for quotations and seller matching</p>
        <div className="mt-8">
          <EmptyState
            icon={ShoppingCart}
            title="Marketplace coming soon"
            description="Request for quotations and seller matching will appear here"
          />
        </div>
      </div>
    </AppShell>
  );
}
