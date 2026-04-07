'use client';

import * as React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  Play, UserCog, StopCircle, ArrowLeft, Circle,
  AlertTriangle, CheckCircle2, XCircle,
} from 'lucide-react';

import { AppShell } from '@/components/layout/AppShell';
import { SectionHeader } from '@/components/shared/SectionHeader';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { NegotiationTimeline } from '@/components/shared/NegotiationTimeline';
import { PriceConvergenceChart } from '@/components/shared/PriceConvergenceChart';
import { HumanOverridePanel } from '@/components/shared/HumanOverridePanel';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { Button } from '@/components/ui/button';

import { useAuth } from '@/hooks/useAuth';
import { useSSE } from '@/hooks/useSSE';
import { api } from '@/lib/api';
import { formatCurrency, cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import type { NegotiationSession, NegotiationOffer, SessionStatus } from '@/types';

// Empty initial — real offers come from the session API response
const INITIAL_OFFERS: NegotiationOffer[] = [];

export default function NegotiationRoomPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.session_id as string;
  const { enterprise } = useAuth();
  const enterpriseId = enterprise?.id;

  // ─── Session data ───────────────────────────────────────────────────────────
  const { data: session } = useQuery<NegotiationSession>({
    queryKey: ['session', sessionId],
    queryFn: () => api.get(`/v1/sessions/${sessionId}`).then(r => r.data.data),
    enabled: !!sessionId,
  });

  // ─── Local real-time state ──────────────────────────────────────────────────
  const [offers, setOffers] = React.useState<NegotiationOffer[]>(INITIAL_OFFERS);
  const [sessionStatus, setSessionStatus] = React.useState<SessionStatus>('ACTIVE');
  const [stallWarning, setStallWarning] = React.useState(false);
  const [agreedPrice, setAgreedPrice] = React.useState<number | null>(null);
  const [showOverride, setShowOverride] = React.useState(false);
  const [showLeaveDialog, setShowLeaveDialog] = React.useState(false);
  const [showEndDialog, setShowEndDialog] = React.useState(false);

  // Sync from fetched session
  React.useEffect(() => {
    if (session) {
      setSessionStatus(session.status);
      if (session.agreed_price) setAgreedPrice(session.agreed_price);
      if (session.offers && session.offers.length > 0) {
        setOffers(session.offers);
      }
    }
  }, [session]);

  // ─── SSE ────────────────────────────────────────────────────────────────────
  const { isConnected } = useSSE({
    sessionId,
    enabled: sessionStatus === 'ACTIVE',
    onEvent: (event, data: any) => {
      switch (event) {
        case 'new_offer':
          setOffers(prev => [...prev, data.offer]);
          break;
        case 'session_agreed':
          setSessionStatus('AGREED');
          setAgreedPrice(data.agreed_price);
          toast.success(`Deal agreed at ${formatCurrency(data.agreed_price)}!`);
          break;
        case 'session_failed':
          setSessionStatus('FAILED');
          toast.error(`Negotiation failed: ${data.reason ?? 'Max rounds reached'}`);
          break;
        case 'stall_detected':
          setStallWarning(true);
          toast.warning('AI negotiation stalled -- consider manual override');
          break;
        case 'round_timeout':
          toast.warning(`Round ${data.timeout_round} timed out`);
          break;
      }
    },
  });

  // ─── Actions ────────────────────────────────────────────────────────────────
  const nextTurnMutation = useMutation({
    mutationFn: () => api.post(`/v1/sessions/${sessionId}/turn`),
    onSuccess: () => toast.success('Next turn triggered'),
    onError: () => toast.error('Failed to trigger next turn'),
  });

  const overrideMutation = useMutation({
    mutationFn: (offer: { price: number; terms: Record<string, string> }) =>
      api.post(`/v1/sessions/${sessionId}/override`, offer),
    onSuccess: () => {
      toast.success('Human override submitted');
      setShowOverride(false);
    },
    onError: () => toast.error('Failed to submit override'),
  });

  const terminateMutation = useMutation({
    mutationFn: () => api.post(`/v1/sessions/${sessionId}/terminate`),
    onSuccess: () => {
      toast.success('Session terminated');
      setSessionStatus('TERMINATED');
      setShowEndDialog(false);
    },
    onError: () => toast.error('Failed to terminate session'),
  });

  // ─── Derived data ──────────────────────────────────────────────────────────
  const buyerOffers = offers.filter(o => o.proposer_role === 'BUYER').map(o => o.price);
  const sellerOffers = offers.filter(o => o.proposer_role === 'SELLER').map(o => o.price);
  const latestRound = offers.length > 0 ? offers[offers.length - 1].round_number : (session?.round_count ?? 0);
  const maxRounds = 20;
  const isActive = sessionStatus === 'ACTIVE';
  const isEnded = sessionStatus === 'AGREED' || sessionStatus === 'FAILED' || sessionStatus === 'TIMEOUT' || sessionStatus === 'WALK_AWAY' || sessionStatus === 'POLICY_BREACH' || sessionStatus === 'TERMINATED';

  // ─── Party display ──────────────────────────────────────────────────────────
  const isYouBuyer = session?.buyer_enterprise_id === enterpriseId;
  const yourRole = isYouBuyer ? 'Buyer' : 'Seller';
  const opponent = isYouBuyer ? session?.seller_name : session?.buyer_name;

  return (
    <AppShell>
      <div className="p-6">

        {/* Header */}
        <div className="bg-secondary border border-border rounded-lg p-6 mb-6">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-lg font-semibold text-foreground">
                  Negotiation {sessionId}
                </h1>
                <StatusBadge status={sessionStatus} />
                {/* Connection indicator */}
                <div className="flex items-center gap-1.5">
                  <Circle className={cn(
                    'h-2 w-2',
                    isConnected ? 'fill-green-500 text-green-500' : 'fill-muted-foreground text-muted-foreground'
                  )} />
                  <span className="text-xs text-muted-foreground">
                    {isConnected ? 'Live' : 'Disconnected'}
                  </span>
                </div>
              </div>
              <p className="text-sm text-muted-foreground">
                You ({yourRole})
                <span className="mx-1">&harr;</span>
                {opponent ?? 'Loading...'}
              </p>
              <div className="flex items-center gap-4 mt-2">
                <span className="text-sm text-muted-foreground">
                  Round: <span className="text-primary font-mono">{latestRound}/{maxRounds}</span>
                </span>
                {agreedPrice && (
                  <span className="text-sm text-green-400 font-medium">
                    Agreed: {formatCurrency(agreedPrice)}
                  </span>
                )}
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowLeaveDialog(true)}
              className="text-muted-foreground hover:text-foreground hover:bg-accent"
            >
              <ArrowLeft className="h-4 w-4 mr-1.5" />
              Leave
            </Button>
          </div>
        </div>

        {/* Banners */}
        {sessionStatus === 'AGREED' && (
          <div className="flex items-center gap-3 bg-green-950 border border-green-900 rounded-lg p-4 mb-6">
            <CheckCircle2 className="h-5 w-5 text-green-400 shrink-0" />
            <div>
              <p className="text-sm font-medium text-green-400">Deal Agreed</p>
              <p className="text-xs text-muted-foreground">
                Final price: {formatCurrency(agreedPrice ?? 0)} -- Proceed to escrow to settle.
              </p>
            </div>
          </div>
        )}

        {sessionStatus === 'FAILED' && (
          <div className="flex items-center gap-3 bg-red-950 border border-red-900 rounded-lg p-4 mb-6">
            <XCircle className="h-5 w-5 text-destructive shrink-0" />
            <div>
              <p className="text-sm font-medium text-destructive">Negotiation Failed</p>
              <p className="text-xs text-muted-foreground">Maximum rounds reached without agreement.</p>
            </div>
          </div>
        )}

        {stallWarning && isActive && (
          <div className="flex items-center gap-3 bg-amber-950 border border-amber-900 rounded-lg p-4 mb-6">
            <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-400">Stall Detected</p>
              <p className="text-xs text-muted-foreground">AI negotiation has stalled -- consider using human override.</p>
            </div>
            <Button
              size="sm"
              onClick={() => { setShowOverride(true); setStallWarning(false); }}
              className="ml-auto bg-primary text-primary-foreground hover:bg-primary/90 text-xs"
            >
              Override
            </Button>
          </div>
        )}

        {/* Timeline */}
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <SectionHeader title="Negotiation Timeline" description={`${offers.length} offers exchanged`} />
          <div className="max-h-96 overflow-y-auto pr-2">
            <NegotiationTimeline offers={offers} sessionStatus={sessionStatus} />
          </div>
        </div>

        {/* Price Convergence Chart */}
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <SectionHeader title="Price Convergence" />
          <PriceConvergenceChart buyerOffers={buyerOffers} sellerOffers={sellerOffers} />
        </div>

        {/* Actions */}
        {!isEnded && (
          <div className="bg-card border border-border rounded-lg p-6 mb-6">
            <div className="flex flex-wrap items-center justify-center gap-4">
              <Button
                onClick={() => nextTurnMutation.mutate()}
                disabled={nextTurnMutation.isPending || !isActive}
                className="bg-primary text-primary-foreground hover:bg-primary/90 px-8 py-3 text-base font-semibold"
              >
                <Play className="h-4 w-4 mr-2" />
                Next Turn
              </Button>
              <Button
                variant="ghost"
                onClick={() => setShowOverride(!showOverride)}
                className="text-foreground hover:bg-accent"
              >
                <UserCog className="h-4 w-4 mr-2" />
                Human Override
              </Button>
              <Button
                variant="outline"
                onClick={() => setShowEndDialog(true)}
                className="text-destructive border-destructive/40 hover:bg-red-950"
              >
                <StopCircle className="h-4 w-4 mr-2" />
                End Session
              </Button>
            </div>
          </div>
        )}

        {/* Human Override Panel */}
        {showOverride && !isEnded && (
          <div className="bg-muted/50 border border-border rounded-lg p-6 mb-6 animate-in fade-in slide-in-from-top-2 duration-200">
            <SectionHeader title="Human Override" description="Submit a manual price and terms to override the AI agent" />
            <HumanOverridePanel
              onSubmit={(offer) => overrideMutation.mutate(offer)}
              isSubmitting={overrideMutation.isPending}
            />
          </div>
        )}

        {/* Leave Dialog */}
        <ConfirmDialog
          open={showLeaveDialog}
          onOpenChange={setShowLeaveDialog}
          title="Leave Negotiation Room"
          description="The negotiation will continue in the background. You can return anytime."
          confirmLabel="Leave"
          onConfirm={() => router.push(ROUTES.NEGOTIATIONS)}
        />

        {/* End Session Dialog */}
        <ConfirmDialog
          open={showEndDialog}
          onOpenChange={setShowEndDialog}
          title="End Negotiation Session"
          description="This will permanently terminate the session. This action cannot be undone."
          confirmLabel="Terminate"
          variant="destructive"
          onConfirm={() => terminateMutation.mutate()}
          isLoading={terminateMutation.isPending}
        />
      </div>
    </AppShell>
  );
}
