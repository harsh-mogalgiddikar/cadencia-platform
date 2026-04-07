import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { ClipboardList } from 'lucide-react';

export default function CompliancePage() {
  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Compliance</h1>
        <p className="text-sm text-muted-foreground mt-1">Audit logs and regulatory export</p>
        <div className="mt-8">
          <EmptyState
            icon={ClipboardList}
            title="Compliance coming soon"
            description="Audit logs and regulatory export will appear here"
          />
        </div>
      </div>
    </AppShell>
  );
}
