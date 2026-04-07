import * as React from 'react';
import { cn } from '@/lib/utils';

export type AdminTab =
  | 'overview'
  | 'enterprises'
  | 'users'
  | 'agents'
  | 'llm-logs'
  | 'broadcast';

interface AdminTabNavProps {
  activeTab: AdminTab;
  onChange: (tab: AdminTab) => void;
}

export function AdminTabNav({ activeTab, onChange }: AdminTabNavProps) {
  const tabs: { id: AdminTab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'enterprises', label: 'Enterprises' },
    { id: 'users', label: 'Users' },
    { id: 'agents', label: 'Agents' },
    { id: 'llm-logs', label: 'LLM Logs' },
    { id: 'broadcast', label: 'Broadcast' },
  ];

  return (
    <div className="sticky top-16 z-10 bg-background py-3 mb-8 overflow-x-auto whitespace-nowrap hide-scrollbar flex">
      <div className="bg-card border border-border rounded-full p-1 inline-flex gap-1">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={cn(
              'rounded-full px-4 py-1.5 text-sm font-medium transition-colors',
              activeTab === tab.id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-accent'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}
