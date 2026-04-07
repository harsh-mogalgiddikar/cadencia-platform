import * as React from 'react';
import { ExternalLink } from 'lucide-react';

interface TxExplorerLinkProps {
  txId: string | number;
  type: 'tx' | 'app';
}

export function TxExplorerLink({ txId, type }: TxExplorerLinkProps) {
  const isApp = type === 'app';
  const urlParams = isApp ? `application/${txId}` : `tx/${txId}`;
  const display = isApp ? `#${txId}` : String(txId).slice(0, 8) + '...';

  return (
    <a
      href={`https://testnet.algoexplorer.io/${urlParams}`}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 font-mono text-xs text-primary hover:underline hover:text-primary/90"
      title={String(txId)}
    >
      {display}
      <ExternalLink className="h-3 w-3" />
    </a>
  );
}
