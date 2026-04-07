'use client';

import { useEffect } from 'react';
import { Wallet, Link2, Unlink, RefreshCw, Loader2, Copy, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';

import { AppShell } from '@/components/layout/AppShell';
import { EmptyState } from '@/components/shared/EmptyState';
import { Button } from '@/components/ui/button';
import { useWallet } from '@/context/WalletContext';
import { truncateAddress, formatCurrency } from '@/lib/utils';

export default function WalletPage() {
  const {
    isLinked, linkedAddress, balance, isLoadingBalance,
    status, error, connectAndLink, unlinkWallet, refreshBalance,
  } = useWallet();

  useEffect(() => {
    if (isLinked) refreshBalance();
  }, [isLinked, refreshBalance]);

  const copyAddress = () => {
    if (linkedAddress) {
      navigator.clipboard.writeText(linkedAddress);
      toast.success('Address copied');
    }
  };

  const isConnecting = status === 'connecting' || status === 'signing' || status === 'submitting';

  return (
    <AppShell>
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-semibold text-foreground">Wallet Management</h1>
        <p className="text-sm text-muted-foreground mt-1">Connect your Algorand wallet via Pera Wallet</p>

        {error && (
          <div className="mt-4 p-3 bg-red-950 border border-destructive/40 rounded-lg text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="mt-8">
          {!isLinked ? (
            <div className="bg-card border border-border rounded-lg p-8 text-center">
              <div className="bg-muted rounded-full p-4 w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                <Wallet className="h-8 w-8 text-muted-foreground" />
              </div>
              <h2 className="text-lg font-medium text-foreground mb-2">No Wallet Connected</h2>
              <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
                Link your Algorand wallet to deploy escrow contracts and fund trades on-chain.
              </p>
              <Button onClick={connectAndLink} disabled={isConnecting} className="bg-primary text-primary-foreground">
                {isConnecting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {status === 'connecting' ? 'Connecting...' : status === 'signing' ? 'Sign in Pera...' : 'Linking...'}
                  </>
                ) : (
                  <>
                    <Link2 className="mr-2 h-4 w-4" />
                    Connect Pera Wallet
                  </>
                )}
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Address Card */}
              <div className="bg-card border border-border rounded-lg p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-foreground">Linked Wallet</h3>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 text-xs text-green-500 bg-green-500/10 px-2 py-1 rounded-full">
                      <span className="w-1.5 h-1.5 bg-green-500 rounded-full" />
                      Connected
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 mb-4">
                  <code className="text-sm font-mono text-foreground bg-muted px-3 py-1.5 rounded flex-1 overflow-hidden text-ellipsis">
                    {linkedAddress}
                  </code>
                  <Button variant="ghost" size="sm" onClick={copyAddress} title="Copy address">
                    <Copy className="h-4 w-4" />
                  </Button>
                  <a
                    href={`https://testnet.algoexplorer.io/address/${linkedAddress}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Button variant="ghost" size="sm" title="View on explorer">
                      <ExternalLink className="h-4 w-4" />
                    </Button>
                  </a>
                </div>

                <Button variant="outline" size="sm" onClick={unlinkWallet} className="text-destructive hover:text-destructive">
                  <Unlink className="mr-2 h-4 w-4" />
                  Unlink Wallet
                </Button>
              </div>

              {/* Balance Card */}
              <div className="bg-card border border-border rounded-lg p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-foreground">Balance</h3>
                  <Button variant="ghost" size="sm" onClick={refreshBalance} disabled={isLoadingBalance}>
                    <RefreshCw className={`h-4 w-4 ${isLoadingBalance ? 'animate-spin' : ''}`} />
                  </Button>
                </div>

                {isLoadingBalance ? (
                  <div className="space-y-2">
                    <div className="h-8 w-32 bg-muted animate-pulse rounded" />
                    <div className="h-4 w-48 bg-muted animate-pulse rounded" />
                  </div>
                ) : balance ? (
                  <div className="space-y-3">
                    <div>
                      <p className="text-2xl font-semibold text-foreground">{balance.algo_balance_algo} ALGO</p>
                      <p className="text-xs text-muted-foreground">{balance.algo_balance_microalgo.toLocaleString()} microALGO</p>
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-xs text-muted-foreground">Min Balance</p>
                        <p className="text-foreground">{(balance.min_balance / 1_000_000).toFixed(3)} ALGO</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Available</p>
                        <p className="text-foreground">{(balance.available_balance / 1_000_000).toFixed(3)} ALGO</p>
                      </div>
                    </div>
                    {balance.opted_in_apps.length > 0 && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Opted-in Applications</p>
                        <div className="flex flex-wrap gap-1">
                          {balance.opted_in_apps.map(app => (
                            <span key={app.app_id} className="text-xs bg-muted px-2 py-0.5 rounded font-mono">
                              {app.app_name ?? `App #${app.app_id}`}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Click refresh to load balance</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
