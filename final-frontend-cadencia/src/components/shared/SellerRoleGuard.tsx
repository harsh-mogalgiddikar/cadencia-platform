'use client';

import { Store } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { EmptyState } from '@/components/shared/EmptyState';

export function SellerRoleGuard({ children }: { children: React.ReactNode }) {
  const { isSeller, enterprise } = useAuth();

  if (!isSeller || !enterprise) {
    return (
      <div className="p-6">
        <EmptyState
          icon={Store}
          title="Seller Profile Access Denied"
          description="This page is only available to sellers. Update your trade role in Settings."
        />
      </div>
    );
  }

  return <>{children}</>;
}
