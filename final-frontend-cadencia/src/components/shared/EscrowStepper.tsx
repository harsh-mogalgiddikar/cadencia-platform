import * as React from 'react';
import { Check, Play, Unlock, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TxExplorerLink } from './TxExplorerLink';
import { cn } from '@/lib/utils';
import type { EscrowStatus } from '@/types';

interface EscrowStepperProps {
  status: EscrowStatus;
  appId?: number | null;
  onAction: (action: 'deploy' | 'fund' | 'release' | 'refund' | 'freeze') => void;
}

export function EscrowStepper({ status, appId, onAction }: EscrowStepperProps) {
  const steps = [
    { key: 'DEPLOYED', label: 'Deployed' },
    { key: 'FUNDED', label: 'Funded' },
    { key: 'RELEASED', label: 'Released' },
  ];

  const getStepIndex = () => {
    switch (status) {
      case 'DEPLOYED': return 0;
      case 'FUNDED': return 1;
      case 'RELEASED': return 2;
      case 'REFUNDED': return 3; // Beyond normal path
      case 'FROZEN': return -1; // Error path
      default: return -1;
    }
  };

  const currentIndex = getStepIndex();
  const isError = status === 'REFUNDED' || status === 'FROZEN';

  return (
    <div className="flex flex-col items-center">
      <div className="flex items-center w-full max-w-3xl justify-between relative mb-6">
        {/* Progress line */}
        <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-0.5 bg-muted z-0">
          <div 
            className="h-full bg-green-500 transition-all duration-500" 
            style={{ width: currentIndex > 0 ? `${(Math.min(currentIndex, 2) / 2) * 100}%` : '0%' }}
          />
        </div>

        {/* Nodes */}
        {steps.map((step, idx) => {
          const isCompleted = currentIndex > idx && !isError;
          const isCurrent = currentIndex === idx && !isError;

          return (
            <div key={step.key} className="flex flex-col items-center relative z-10 w-24">
              <div 
                className={cn(
                  'h-8 w-8 rounded-full flex items-center justify-center text-sm font-bold bg-background transition-colors',
                  isCompleted ? 'bg-green-500 text-green-950 border-2 border-green-500' :
                  isCurrent ? 'border-2 border-green-500 text-green-500 ring-4 ring-green-950/20' : 
                  'bg-muted text-muted-foreground border-2 border-border'
                )}
              >
                {isCompleted ? <Check className="h-4 w-4" /> : idx + 1}
              </div>
              <span 
                className={cn(
                  'mt-3 text-xs font-medium',
                  isCompleted || isCurrent ? 'text-foreground' : 'text-muted-foreground'
                )}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      {isError && (
        <div className="mb-6 flex items-center gap-2 text-destructive bg-red-950/20 px-4 py-2 rounded-md border border-red-900/30">
          <AlertCircle className="h-4 w-4" />
          <span className="text-sm font-medium">
            Escrow State: {status}
          </span>
        </div>
      )}

      {/* Contract Details */}
      <div className="text-sm text-muted-foreground flex items-center gap-2 mb-6 bg-accent px-4 py-2 rounded-full">
        <span>Current Status: <strong className={cn(isError ? 'text-destructive' : 'text-foreground')}>{status}</strong></span>
        {appId && (
          <>
            <span>&bull;</span>
            <span>Contract:</span>
            <TxExplorerLink txId={appId} type="app" />
          </>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3 justify-center min-h-[40px]">
        {status === 'DEPLOYED' && (
          <Button onClick={() => onAction('fund')} className="bg-primary text-primary-foreground">
            <Play className="h-4 w-4 mr-2" />
            Fund via Pera Wallet
          </Button>
        )}
        {status === 'FUNDED' && (
          <>
            <Button onClick={() => onAction('release')} className="bg-green-600 text-white hover:bg-green-700">
              <Unlock className="h-4 w-4 mr-2" />
              Release
            </Button>
            <Button variant="outline" onClick={() => onAction('refund')} className="border-amber-600 text-amber-500 hover:bg-amber-950">
              Refund
            </Button>
            <Button variant="outline" onClick={() => onAction('freeze')} className="border-blue-600 text-blue-500 hover:bg-blue-950">
              Freeze
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
