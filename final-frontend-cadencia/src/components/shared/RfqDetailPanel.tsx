'use client';

import * as React from 'react';
import { Loader2 } from 'lucide-react';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { AsyncPollingStatus } from '@/components/shared/AsyncPollingStatus';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { Button } from '@/components/ui/button';
import { formatDate } from '@/lib/utils';
import type { RFQ, SellerMatch } from '@/types';

interface RfqDetailPanelProps {
  rfq: RFQ;
  matches: SellerMatch[];
  matchesLoading: boolean;
  onConfirm: (match: SellerMatch) => void;
  isConfirming: boolean;
}

const FIELD_LABELS: Record<string, string> = {
  product: 'Product',
  hsn: 'HSN Code',
  quantity: 'Quantity',
  budget_min: 'Budget Min',
  budget_max: 'Budget Max',
  delivery_days: 'Delivery',
  geography: 'Geography',
};

export function RfqDetailPanel({ rfq, matches, matchesLoading, onConfirm, isConfirming }: RfqDetailPanelProps) {
  const [confirmTarget, setConfirmTarget] = React.useState<SellerMatch | null>(null);

  const parsedEntries = React.useMemo(() => {
    if (!rfq.parsed_fields) return [];
    return Object.entries(rfq.parsed_fields).map(([key, val]) => ({
      label: FIELD_LABELS[key] ?? key,
      value: key === 'delivery_days' ? `${val} days` : String(val),
    }));
  }, [rfq.parsed_fields]);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <h3 className="text-sm font-semibold text-foreground">RFQ #{rfq.id}</h3>
          <StatusBadge status={rfq.status} />
        </div>
        <p className="text-xs text-muted-foreground">{formatDate(rfq.created_at)}</p>
      </div>

      {/* Raw text */}
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Description</p>
        <p className="text-sm text-foreground leading-relaxed">{rfq.raw_text}</p>
      </div>

      {/* Polling status for DRAFT/PARSED */}
      {(rfq.status === 'DRAFT' || rfq.status === 'PARSED') && (
        <AsyncPollingStatus status={rfq.status} />
      )}

      {/* Parsed fields */}
      {parsedEntries.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-2">Parsed Fields (AI-extracted)</p>
          <div className="grid grid-cols-2 gap-3">
            {parsedEntries.map(({ label, value }) => (
              <div key={label}>
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="text-sm font-medium text-foreground">{value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Matches */}
      {rfq.status === 'MATCHED' && (
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-3">Top Matches (AI similarity)</p>
          {matchesLoading ? (
            <div className="flex items-center gap-2 py-4">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Loading matches...</span>
            </div>
          ) : matches.length === 0 ? (
            <p className="text-sm text-muted-foreground py-2">No matches found</p>
          ) : (
            <div className="space-y-2">
              {matches.map((m) => (
                <div
                  key={m.enterprise_id}
                  className="flex items-center justify-between p-3 bg-muted rounded-lg border border-border"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-muted-foreground">#{m.rank}</span>
                      <span className="text-sm font-medium text-foreground truncate">{m.enterprise_name}</span>
                    </div>
                    {m.capabilities && m.capabilities.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {m.capabilities.map((c) => (
                          <span key={c} className="text-xs bg-secondary text-secondary-foreground px-1.5 py-0.5 rounded">
                            {c}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-3 shrink-0 ml-3">
                    <span className="text-sm font-semibold text-primary">{m.score}%</span>
                    <Button
                      size="sm"
                      onClick={() => setConfirmTarget(m)}
                      className="bg-primary text-primary-foreground hover:bg-primary/90 text-xs px-3 py-1 h-7"
                    >
                      Confirm
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {rfq.status === 'CONFIRMED' && (
        <AsyncPollingStatus status="CONFIRMED" />
      )}

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={!!confirmTarget}
        onOpenChange={(open) => { if (!open) setConfirmTarget(null); }}
        title="Start AI Negotiation"
        description={`Start AI negotiation with ${confirmTarget?.enterprise_name}? This cannot be undone.`}
        confirmLabel="Start Negotiation"
        onConfirm={() => {
          if (confirmTarget) {
            onConfirm(confirmTarget);
            setConfirmTarget(null);
          }
        }}
        isLoading={isConfirming}
      />
    </div>
  );
}
