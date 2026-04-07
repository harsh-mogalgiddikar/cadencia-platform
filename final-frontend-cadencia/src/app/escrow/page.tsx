'use client';

import * as React from 'react';
import Link from 'next/link';
import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query';
import { Landmark, AlertCircle, History } from 'lucide-react';
import { toast } from 'sonner';

import { AppShell } from '@/components/layout/AppShell';
import { SectionHeader } from '@/components/shared/SectionHeader';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { Button } from '@/components/ui/button';
import { EscrowStepper } from '@/components/shared/EscrowStepper';
import { PeraFundWizard } from '@/components/shared/PeraFundWizard';
import { TxExplorerLink } from '@/components/shared/TxExplorerLink';
import { AuthGuard } from '@/components/shared/AuthGuard';

import { useAuth } from '@/hooks/useAuth';
import { api } from '@/lib/api';
import { formatCurrency, formatDate } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import type { NegotiationSession, Escrow, Settlement } from '@/types';

export default function EscrowPage() {
  const queryClient = useQueryClient();
  const { isAdmin } = useAuth();
  
  const [selectedSessionId, setSelectedSessionId] = React.useState<string | null>(null);
  const [showPeraWizard, setShowPeraWizard] = React.useState(false);
  const [actionData, setActionData] = React.useState<{ type: string; escrowId: string; sessionId: string } | null>(null);

  // Fetch all sessions (to find active escrows)
  const { data: sessions = [], isLoading: isLoadingSessions } = useQuery<NegotiationSession[]>({
    queryKey: ['sessions'],
    queryFn: () => api.get('/v1/sessions').then(r => r.data.data),
  });

  // Fetch escrow state for each session
  const escrowQueries = useQueries({
    queries: sessions.map((s) => ({
      queryKey: ['escrow', s.session_id],
      queryFn: () => api.get(`/v1/escrow/${s.session_id}`).then((r) => r.data.data as Escrow | { status: 'NOT_DEPLOYED' }),
      staleTime: 60_000,
    })),
  });

  // Combine data
  const escrows = sessions.map((s, idx) => {
    const p = escrowQueries[idx];
    const e = p.data && 'escrow_id' in p.data ? (p.data as Escrow) : null;
    return { session: s, escrow: e, isLoading: p.isLoading };
  }).filter(x => x.escrow || x.session.status === 'AGREED');

  // Auto-select first escrow if none selected
  React.useEffect(() => {
    if (!selectedSessionId && escrows.length > 0) {
      setSelectedSessionId(escrows[0].session.session_id);
    }
  }, [escrows, selectedSessionId]);

  const selectedEntry = escrows.find(x => x.session.session_id === selectedSessionId);
  const selectedEscrow = selectedEntry?.escrow;

  // Settlements History Query
  const { data: settlements = [], isLoading: isLoadingSettlements } = useQuery<Settlement[]>({
    queryKey: ['settlements', selectedEscrow?.escrow_id],
    queryFn: () => api.get(`/v1/escrow/${selectedEscrow?.escrow_id}/settlements`).then(r => r.data.data),
    enabled: !!selectedEscrow?.escrow_id,
  });

  // Generic Escrow Action Mutation
  const actionMutation = useMutation({
    mutationFn: (param: { url: string; payload?: unknown }) => api.post(param.url, param.payload),
    onSuccess: () => {
      toast.success('Action successful');
      if (selectedSessionId) {
        queryClient.invalidateQueries({ queryKey: ['escrow', selectedSessionId] });
        if (selectedEscrow?.escrow_id) queryClient.invalidateQueries({ queryKey: ['settlements', selectedEscrow.escrow_id] });
      }
      setActionData(null);
      setShowPeraWizard(false);
    },
    onError: () => {
      toast.error('Action failed');
      setActionData(null);
    },
  });

  const handleAction = (type: 'deploy' | 'fund' | 'release' | 'refund' | 'freeze', sessionId: string, escrowId?: string) => {
    if (type === 'fund') {
      setShowPeraWizard(true);
      return;
    }
    setActionData({ type, escrowId: escrowId || '', sessionId });
  };

  const confirmAction = () => {
    if (!actionData) return;
    const { type, escrowId, sessionId } = actionData;
    let url = '';
    
    // Fallback legacy fund for testing without wallet if needed, though Pera is preferred
    if (type === 'deploy') url = `/v1/escrow/${sessionId}/deploy`;
    else if (type === 'fund-legacy') url = `/v1/escrow/${escrowId}/fund`; 
    else url = `/v1/escrow/${escrowId}/${type}`;

    actionMutation.mutate({ url });
  };

  return (
    <AppShell>
      <AuthGuard>
        <div className="p-6 space-y-8">
          
          {/* Header */}
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Landmark className="h-6 w-6 text-primary" />
              Escrow & Settlements
            </h1>
            <p className="text-muted-foreground mt-2">Manage smart contract escrows and monitor transaction settlements.</p>
          </div>

          {/* Stepper Pipeline */}
          {selectedEntry && (
            <div className="bg-card border border-border rounded-lg p-6">
              <div className="mb-8">
                <SectionHeader title={`Pipeline: ${selectedEntry.session.session_id.slice(0, 12)}`} description="Current state of the selected negotiation's escrow" />
              </div>
              {selectedEscrow ? (
                <EscrowStepper 
                  status={selectedEscrow.status} 
                  appId={selectedEscrow.algo_app_id}
                  onAction={(action) => handleAction(action, selectedEntry.session.session_id, selectedEscrow.escrow_id)}
                />
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center space-y-4">
                  <div className="bg-muted p-4 rounded-full">
                    <AlertCircle className="h-8 w-8 text-muted-foreground" />
                  </div>
                  <div>
                    <h3 className="font-medium text-foreground">Contract Not Deployed</h3>
                    <p className="text-sm text-muted-foreground max-w-sm mt-1">This negotiation has reached an agreement, but the escrow contract hasn&apos;t been deployed yet.</p>
                  </div>
                  {isAdmin && (
                    <Button onClick={() => handleAction('deploy', selectedEntry.session.session_id)} className="mt-4">
                      Deploy Contract
                    </Button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Active Escrows Table */}
          <div className="bg-card border border-border rounded-lg overflow-hidden">
             <div className="px-6 pt-6 pb-2">
               <SectionHeader title="Active Escrows" />
             </div>
             <div className="w-full overflow-x-auto pb-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-xs font-semibold text-muted-foreground text-left uppercase tracking-wider">
                    <th className="px-6 py-4">Session ID</th>
                    <th className="px-6 py-4">Parties</th>
                    <th className="px-6 py-4">Amount</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Contract</th>
                    <th className="px-6 py-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoadingSessions ? (
                    <tr><td colSpan={6} className="px-6 py-8 text-center text-muted-foreground">Loading escrows...</td></tr>
                  ) : escrows.length === 0 ? (
                    <tr><td colSpan={6} className="px-6 py-8 text-center text-muted-foreground">No active escrows found.</td></tr>
                  ) : (
                    escrows.map(({ session, escrow }) => (
                      <tr
                        key={session.session_id}
                        className={`border-b border-border hover:bg-muted/50 transition-colors cursor-pointer ${selectedSessionId === session.session_id ? 'bg-muted/30' : ''}`}
                        onClick={() => {
                          setSelectedSessionId(session.session_id);
                          setShowPeraWizard(false);
                        }}
                      >
                        <td className="px-6 py-4 font-mono text-primary">
                          <Link href={`${ROUTES.NEGOTIATIONS}/${session.session_id}`} className="hover:underline">
                            {session.session_id.slice(0, 12)}
                          </Link>
                        </td>
                        <td className="px-6 py-4 font-medium">
                          {escrow?.buyer_name || session.buyer_name || session.buyer_enterprise_id.slice(0, 8)} <span className="text-muted-foreground mx-1">&rarr;</span> {escrow?.seller_name || session.seller_name || session.seller_enterprise_id.slice(0, 8)}
                        </td>
                        <td className="px-6 py-4 font-semibold">
                          {escrow ? `${escrow.amount_algo} ALGO` : formatCurrency(session.agreed_price || 0)}
                        </td>
                        <td className="px-6 py-4">
                          <StatusBadge status={escrow ? escrow.status : 'AGREED'} />
                        </td>
                        <td className="px-6 py-4">
                          {escrow?.algo_app_id ? <TxExplorerLink txId={escrow.algo_app_id} type="app" /> : <span className="text-muted-foreground">Pending</span>}
                        </td>
                        <td className="px-6 py-4 text-right">
                          {escrow ? (
                            <Button size="sm" variant="ghost" className="text-xs" onClick={(e) => { e.stopPropagation(); setSelectedSessionId(session.session_id); }}>
                              View Details
                            </Button>
                          ) : isAdmin ? (
                            <Button size="sm" variant="outline" className="text-xs" onClick={(e) => { e.stopPropagation(); handleAction('deploy', session.session_id); }}>
                              Deploy
                            </Button>
                          ) : (
                            <span className="text-xs text-muted-foreground">Waiting for Admin</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pera Wallet Wizard */}
          {showPeraWizard && selectedEscrow && selectedEscrow.status === 'DEPLOYED' && (
            <PeraFundWizard 
              escrowId={selectedEscrow.escrow_id}
              onFundComplete={() => {
                setShowPeraWizard(false);
                queryClient.invalidateQueries({ queryKey: ['escrow', selectedSessionId] });
              }} 
              onCancel={() => setShowPeraWizard(false)}
            />
          )}

          {/* Settlements History */}
          {selectedEscrow && (
            <div className="bg-card border border-border rounded-lg overflow-hidden">
              <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/20">
                <div className="flex items-center gap-2">
                  <History className="h-5 w-5 text-muted-foreground" />
                  <h3 className="font-semibold text-foreground">Settlements History</h3>
                </div>
                <span className="text-xs font-mono text-muted-foreground bg-muted px-2 py-1 rounded">
                  ESCROW: {selectedEscrow.escrow_id.slice(0, 12)}
                </span>
              </div>
              <div className="w-full overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs font-semibold text-muted-foreground text-left uppercase tracking-wider bg-muted/10">
                      <th className="px-6 py-4">Action</th>
                      <th className="px-6 py-4">Amount</th>
                      <th className="px-6 py-4">Blockchain Tx ID</th>
                      <th className="px-6 py-4 text-right">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isLoadingSettlements ? (
                      <tr><td colSpan={4} className="px-6 py-8 text-center text-muted-foreground">Loading history...</td></tr>
                    ) : settlements.length === 0 ? (
                      <tr><td colSpan={4} className="px-6 py-8 text-center text-muted-foreground">No settlements recorded yet.</td></tr>
                    ) : (
                      settlements.map((s) => (
                        <tr key={s.settlement_id} className="border-b border-border hover:bg-muted/30">
                          <td className="px-6 py-4">
                            <span className="bg-muted px-2 py-1 rounded-md text-xs font-medium border border-border">
                              Milestone {s.milestone_index}
                            </span>
                          </td>
                          <td className="px-6 py-4 font-semibold text-foreground">{(s.amount_microalgo / 1_000_000).toFixed(3)} ALGO</td>
                          <td className="px-6 py-4">
                            <TxExplorerLink txId={s.tx_id} type="tx" />
                          </td>
                          <td className="px-6 py-4 text-right text-muted-foreground text-xs whitespace-nowrap">
                            {formatDate(s.settled_at)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          
        </div>

        {/* Action Confirm Dialog */}
        <ConfirmDialog
          open={!!actionData}
          onOpenChange={(v) => !v && setActionData(null)}
          title={`Confirm ${actionData?.type.toUpperCase()}`}
          description={`Are you sure you want to perform the ${actionData?.type} action on this contract? This blockchain action is irreversible.`}
          confirmLabel={`Proceed with ${actionData?.type}`}
          variant={actionData?.type === 'refund' || actionData?.type === 'freeze' ? 'destructive' : 'default'}
          onConfirm={confirmAction}
          isLoading={actionMutation.isPending}
        />

      </AuthGuard>
    </AppShell>
  );
}
