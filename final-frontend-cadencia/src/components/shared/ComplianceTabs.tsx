import * as React from 'react';
import { FileText, Receipt } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ComplianceTabsProps {
  activeTab: 'audit' | 'fema' | 'gst';
  onTabChange: (tab: 'audit' | 'fema' | 'gst') => void;
}

export function ComplianceTabs({ activeTab, onTabChange }: ComplianceTabsProps) {
  const tabs = [
    { id: 'audit', label: 'Audit Log', icon: FileText },
    { id: 'fema', label: 'FEMA', icon: FileText },
    { id: 'gst', label: 'GST', icon: Receipt },
  ] as const;

  return (
    <div className="flex border-b border-border mb-6">
      {tabs.map(tab => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            'flex items-center gap-2 px-6 py-3 border-b-2 text-sm font-medium transition-colors',
            activeTab === tab.id 
              ? 'border-primary text-primary' 
              : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
          )}
        >
          <tab.icon className="h-4 w-4" />
          {tab.label}
        </button>
      ))}
    </div>
  );
}
