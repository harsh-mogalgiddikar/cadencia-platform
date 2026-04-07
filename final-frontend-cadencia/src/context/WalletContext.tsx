'use client';

import React, { createContext, useContext, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
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
  signAndSubmitFundTxn: (escrowId: string) => Promise<{ txid: string; confirmed_round: number }>;
}

const WalletContext = createContext<WalletContextValue | null>(null);

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const { enterprise, refreshProfile } = useAuth();
  const [status, setStatus] = useState<WalletStatus>(
    enterprise?.algorand_wallet ? 'linked' : 'idle'
  );
  const [balance, setBalance] = useState<WalletBalance | null>(null);
  const [isLoadingBalance, setIsLoadingBalance] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isLinked = !!enterprise?.algorand_wallet;
  const linkedAddress = enterprise?.algorand_wallet ?? null;

  const connectAndLink = useCallback(async () => {
    setError(null);
    setStatus('connecting');

    try {
      // Dynamically import Pera wallet to avoid SSR issues
      const { PeraWalletConnect } = await import('@perawallet/connect');
      const peraWallet = new PeraWalletConnect();

      // Connect to Pera Wallet
      const accounts = await peraWallet.connect();
      if (!accounts || accounts.length === 0) {
        throw new Error('No accounts returned from Pera Wallet');
      }
      const address = accounts[0];

      // Get challenge from backend
      setStatus('signing');
      const { data: challengeRes } = await api.get('/v1/wallet/challenge');
      const challenge = challengeRes.data;

      // Sign the challenge message with Pera Wallet
      const encoder = new TextEncoder();
      const messageBytes = encoder.encode(challenge.challenge);
      const signedBytes = await peraWallet.signData(
        [{ data: messageBytes, message: challenge.challenge }],
        address
      );

      // Submit signed challenge to backend to link wallet
      setStatus('submitting');
      await api.post('/v1/wallet/link', {
        algorand_address: address,
        signature: btoa(String.fromCharCode(...new Uint8Array(signedBytes[0]))),
        challenge: challenge.challenge,
      });

      // Refresh enterprise profile to pick up new wallet address
      await refreshProfile();
      setStatus('linked');
      toast.success('Wallet linked successfully');

      // Disconnect Pera (session-based)
      peraWallet.disconnect();
    } catch (err: any) {
      setError(err.message || 'Failed to connect wallet');
      setStatus('error');
      toast.error(err.message || 'Failed to connect wallet');
    }
  }, [refreshProfile]);

  const unlinkWallet = useCallback(async () => {
    try {
      await api.delete('/v1/wallet/link');
      await refreshProfile();
      setBalance(null);
      setStatus('idle');
      toast.success('Wallet unlinked');
    } catch (err: any) {
      toast.error('Failed to unlink wallet');
    }
  }, [refreshProfile]);

  const refreshBalance = useCallback(async () => {
    if (!isLinked) return;
    setIsLoadingBalance(true);
    try {
      const { data } = await api.get('/v1/wallet/balance');
      setBalance(data.data);
    } catch {
      toast.error('Failed to fetch wallet balance');
    } finally {
      setIsLoadingBalance(false);
    }
  }, [isLinked]);

  const signAndSubmitFundTxn = useCallback(async (escrowId: string) => {
    setError(null);
    setStatus('connecting');

    try {
      const { PeraWalletConnect } = await import('@perawallet/connect');
      const peraWallet = new PeraWalletConnect();
      const accounts = await peraWallet.connect();
      const address = accounts[0];

      // Get unsigned transactions from backend
      setStatus('signing');
      const { data: buildRes } = await api.get(`/v1/escrow/${escrowId}/build-fund-txn`);
      const { unsigned_transactions } = buildRes.data;

      // Decode and sign transactions with Pera
      const { decodeUnsignedTransaction } = await import('algosdk');
      const txns = unsigned_transactions.map((b64: string) =>
        decodeUnsignedTransaction(Uint8Array.from(atob(b64), c => c.charCodeAt(0)))
      );
      const signedTxns = await peraWallet.signTransaction([
        txns.map((txn: any) => ({ txn })),
      ]);

      // Submit signed transactions to backend
      setStatus('submitting');
      const signedB64 = signedTxns.map((s: Uint8Array) =>
        btoa(String.fromCharCode(...new Uint8Array(s)))
      );
      const { data: submitRes } = await api.post(`/v1/escrow/${escrowId}/submit-signed-fund`, {
        signed_transactions: signedB64,
      });

      setStatus('linked');
      peraWallet.disconnect();
      toast.success(`Escrow funded! TX: ${submitRes.data.txid.slice(0, 12)}...`);
      return submitRes.data;
    } catch (err: any) {
      setError(err.message || 'Fund transaction failed');
      setStatus('error');
      toast.error(err.message || 'Fund transaction failed');
      throw err;
    }
  }, []);

  return (
    <WalletContext.Provider value={{
      isLinked,
      linkedAddress,
      balance,
      isLoadingBalance,
      status,
      error,
      connectAndLink,
      unlinkWallet,
      refreshBalance,
      signAndSubmitFundTxn,
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
