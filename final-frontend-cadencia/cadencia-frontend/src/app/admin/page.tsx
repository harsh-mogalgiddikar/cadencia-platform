import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { ShieldCheck } from 'lucide-react';

export default function AdminPage() {
  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Admin Panel</h1>
        <p className="text-sm text-muted-foreground mt-1">System administration and monitoring</p>
        <div className="mt-8">
          <EmptyState
            icon={ShieldCheck}
            title="Admin Panel coming soon"
            description="System administration and monitoring will appear here"
          />
        </div>
      </div>
    </AppShell>
  );
}
