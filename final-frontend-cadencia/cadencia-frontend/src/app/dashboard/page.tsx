import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { LayoutDashboard } from 'lucide-react';

export default function DashboardPage() {
  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">Your trade activity overview</p>
        <div className="mt-8">
          <EmptyState
            icon={LayoutDashboard}
            title="Dashboard coming soon"
            description="Trade metrics and recent activity will appear here"
          />
        </div>
      </div>
    </AppShell>
  );
}
