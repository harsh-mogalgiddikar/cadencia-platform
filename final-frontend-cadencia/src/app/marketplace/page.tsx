'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { useQueries, useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Plus, RotateCcw, FileText, ChevronDown } from 'lucide-react';

import { AppShell } from '@/components/layout/AppShell';
import { SectionHeader } from '@/components/shared/SectionHeader';
import { DataTable } from '@/components/shared/DataTable';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { TextareaWithButton } from '@/components/shared/TextareaWithButton';
import { RfqDetailPanel } from '@/components/shared/RfqDetailPanel';
import { Button } from '@/components/ui/button';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from '@/components/ui/sheet';

import { api } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import type { RFQ, SellerMatch } from '@/types';

const INITIAL_RFQ_IDS = ['rfq-001', 'rfq-002', 'rfq-003'];
const STATUS_OPTIONS = ['All', 'DRAFT', 'PARSED', 'MATCHED', 'CONFIRMED'] as const;

export default function MarketplacePage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  // ─── State ──────────────────────────────────────────────────────────────────
  const [formExpanded, setFormExpanded] = React.useState(false);
  const [rfqText, setRfqText] = React.useState('');
  const [selectedRfqId, setSelectedRfqId] = React.useState<string | null>(null);
  const [filter, setFilter] = React.useState<string>('All');
  const [mobileSheetOpen, setMobileSheetOpen] = React.useState(false);
  const [rfqIds, setRfqIds] = React.useState(INITIAL_RFQ_IDS);

  // ─── Fetch all RFQs ────────────────────────────────────────────────────────
  const rfqQueries = useQueries({
    queries: rfqIds.map(id => ({
      queryKey: ['rfq', id],
      queryFn: () => api.get(`/v1/marketplace/rfq/${id}`).then(r => r.data.data as RFQ),
    })),
  });
  const rfqsLoading = rfqQueries.some(q => q.isLoading);
  const allRfqs: RFQ[] = rfqQueries.filter(q => q.isSuccess && q.data).map(q => q.data!);

  // ─── Filter ─────────────────────────────────────────────────────────────────
  const filteredRfqs = React.useMemo(() => {
    if (filter === 'All') return allRfqs;
    return allRfqs.filter(r => r.status === filter);
  }, [allRfqs, filter]);

  // ─── Selected RFQ ──────────────────────────────────────────────────────────
  const selectedRfq = allRfqs.find(r => r.id === selectedRfqId) ?? null;

  // ─── Matches for selected RFQ ──────────────────────────────────────────────
  const { data: matches = [], isLoading: matchesLoading } = useQuery<SellerMatch[]>({
    queryKey: ['rfq', selectedRfqId, 'matches'],
    queryFn: () => api.get(`/v1/marketplace/rfq/${selectedRfqId}/matches`).then(r => r.data.data),
    enabled: !!selectedRfqId && selectedRfq?.status === 'MATCHED',
  });

  // ─── Polling for DRAFT/PARSED RFQs ────────────────────────────────────────
  React.useEffect(() => {
    if (!selectedRfq || !['DRAFT', 'PARSED'].includes(selectedRfq.status)) return;

    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['rfq', selectedRfq.id] });
    }, 3000);

    return () => clearInterval(interval);
  }, [selectedRfq, queryClient]);

  // ─── Submit new RFQ ────────────────────────────────────────────────────────
  const submitMutation = useMutation({
    mutationFn: async (rawText: string) => {
      const res = await api.post('/v1/marketplace/rfq', { raw_text: rawText });
      return res.data.data as { rfq_id: string; status: string };
    },
    onSuccess: (data) => {
      toast.success(`RFQ submitted! ID: ${data.rfq_id}`);
      setRfqText('');
      setFormExpanded(false);
      // Add new RFQ ID to the list for fetching
      if (!rfqIds.includes(data.rfq_id)) {
        setRfqIds(prev => [...prev, data.rfq_id]);
      }
      setSelectedRfqId(data.rfq_id);
      // Invalidate to refetch
      queryClient.invalidateQueries({ queryKey: ['rfq', data.rfq_id] });
    },
    onError: () => {
      toast.error('Failed to submit RFQ');
    },
  });

  // ─── Confirm match ─────────────────────────────────────────────────────────
  const confirmMutation = useMutation({
    mutationFn: async (match: SellerMatch) => {
      const res = await api.post(`/v1/marketplace/rfq/${selectedRfqId}/confirm`, {
        seller_enterprise_id: match.enterprise_id,
      });
      return res.data.data as { session_id: string };
    },
    onSuccess: (data) => {
      toast.success('Negotiation session started!');
      router.push(`${ROUTES.NEGOTIATIONS}/${data.session_id}`);
    },
    onError: () => {
      toast.error('Failed to start negotiation');
    },
  });

  // ─── Row click handler ─────────────────────────────────────────────────────
  const handleRowClick = (rfq: RFQ) => {
    setSelectedRfqId(rfq.id);
    // On mobile open sheet
    if (window.innerWidth < 1024) {
      setMobileSheetOpen(true);
    }
  };

  // ─── Refresh all ───────────────────────────────────────────────────────────
  const handleRefresh = () => {
    rfqIds.forEach(id => {
      queryClient.invalidateQueries({ queryKey: ['rfq', id] });
    });
  };

  // ─── Detail content (reused in desktop panel and mobile sheet) ─────────────
  const detailContent = selectedRfq ? (
    <RfqDetailPanel
      rfq={selectedRfq}
      matches={matches}
      matchesLoading={matchesLoading}
      onConfirm={(match) => confirmMutation.mutate(match)}
      isConfirming={confirmMutation.isPending}
    />
  ) : (
    <div className="flex items-center justify-center h-full py-16">
      <p className="text-sm text-muted-foreground">Select an RFQ to view details</p>
    </div>
  );

  return (
    <AppShell>
      <div className="p-6">

        {/* Section 1: New RFQ Form */}
        <div className="bg-card border border-border rounded-lg p-6 mb-8">
          <SectionHeader
            title="Request for Quotation"
            action={{
              label: formExpanded ? 'Cancel' : 'New RFQ',
              icon: formExpanded ? undefined : Plus,
              onClick: () => setFormExpanded(!formExpanded),
            }}
          />
          {formExpanded && (
            <div className="animate-in fade-in slide-in-from-top-2 duration-200">
              <p className="text-sm text-muted-foreground mb-3">
                Describe your requirement in natural language. AI will parse and match sellers.
              </p>
              <TextareaWithButton
                placeholder="Need 500 metric tons of HR Coil, IS 2062 grade, delivery to Mumbai port within 45 days. Budget: ₹38,000-42,000 per MT."
                buttonText="Submit RFQ"
                value={rfqText}
                onChange={setRfqText}
                onSubmit={() => submitMutation.mutate(rfqText)}
                isLoading={submitMutation.isPending}
              />
            </div>
          )}
        </div>

        {/* Section 2: RFQ List + Detail Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Left: RFQ List */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between border-b border-border pb-3 mb-4">
              <h3 className="text-base font-semibold text-foreground">Your RFQs</h3>
              <div className="flex items-center gap-2">
                {/* Filter dropdown */}
                <div className="relative">
                  <select
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    className="appearance-none bg-muted border border-border rounded-md px-3 py-1.5 pr-8 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
                  >
                    {STATUS_OPTIONS.map(opt => (
                      <option key={opt} value={opt}>{opt === 'All' ? 'All' : opt}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
                </div>

                {/* Refresh */}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRefresh}
                  className="text-primary hover:bg-secondary"
                >
                  <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
                  Refresh
                </Button>
              </div>
            </div>

            <DataTable<RFQ>
              columns={[
                {
                  key: 'id',
                  label: 'RFQ ID',
                  render: (v) => <span className="text-primary font-mono text-xs">{String(v)}</span>,
                },
                {
                  key: 'raw_text',
                  label: 'Description',
                  render: (v) => {
                    const s = String(v);
                    return (
                      <span className="text-foreground" title={s}>
                        {s.length > 40 ? s.slice(0, 40) + '...' : s}
                      </span>
                    );
                  },
                },
                {
                  key: 'status',
                  label: 'Status',
                  render: (v) => <StatusBadge status={String(v)} />,
                },
                {
                  key: 'created_at',
                  label: 'Created',
                  sortable: true,
                  render: (v) => <span className="text-muted-foreground text-xs">{formatDate(String(v))}</span>,
                },
              ]}
              data={filteredRfqs}
              isLoading={rfqsLoading}
              keyExtractor={(row) => row.id}
              onRowClick={handleRowClick}
              emptyState={{ icon: FileText, title: 'No RFQs yet', description: 'Submit your first RFQ above' }}
            />
          </div>

          {/* Right: Detail Panel (desktop) */}
          <div className="hidden lg:block">
            <div className="bg-card border border-border rounded-lg p-5 sticky top-20">
              <h3 className="text-base font-semibold text-foreground border-b border-border pb-3 mb-4">
                {selectedRfq ? `RFQ #${selectedRfq.id}` : 'RFQ Details'}
              </h3>
              {detailContent}
            </div>
          </div>
        </div>

        {/* Mobile Sheet for Detail Panel */}
        <Sheet open={mobileSheetOpen} onOpenChange={setMobileSheetOpen}>
          <SheetContent side="right" className="bg-card border-border w-full sm:max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="text-foreground">
                {selectedRfq ? `RFQ #${selectedRfq.id}` : 'RFQ Details'}
              </SheetTitle>
            </SheetHeader>
            <div className="mt-4">
              {detailContent}
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </AppShell>
  );
}
