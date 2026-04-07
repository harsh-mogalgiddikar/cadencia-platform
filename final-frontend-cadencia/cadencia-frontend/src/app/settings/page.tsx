import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { Settings } from 'lucide-react';

export default function SettingsPage() {
  return (
    <AppShell>
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">Enterprise profile and configuration</p>
        <div className="mt-8">
          <EmptyState
            icon={Settings}
            title="Settings coming soon"
            description="Enterprise profile and configuration will appear here"
          />
        </div>
      </div>
    </AppShell>
  );
}
