'use client';

import React, { createContext, useContext, useState } from 'react';
import type { WalletBalance } from '@/types';

type WalletStatus = 'idle' | 'connecting' | 'signing' | 'submitting' | 'linked' | 'error';

interface WalletContextValue {
  isLinked: boolean;
  linkedAddress: string | null;
  balance: WalletBalance | null;
  isLoadingBalance: boolean;
  status: WalletStatus;
  error: string | null;
  connectAndLink: () => Promise<void>;
  unlinkWallet: () => Promise<void>;
  refreshBalance: () => Promise<void>;
  signAndSubmitFundTxn: (escrowId: string) => Promise<void>;
}

const WalletContext = createContext<WalletContextValue | null>(null);

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const [status] = useState<WalletStatus>('idle');

  const stub = async () => {};

  return (
    <WalletContext.Provider value={{
      isLinked: false,
      linkedAddress: null,
      balance: null,
      isLoadingBalance: false,
      status,
      error: null,
      connectAndLink: stub,
      unlinkWallet: stub,
      refreshBalance: stub,
      signAndSubmitFundTxn: stub,
    }}>
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet() {
  const ctx = useContext(WalletContext);
  if (!ctx) throw new Error('useWallet must be used inside WalletProvider');
  return ctx;
}
