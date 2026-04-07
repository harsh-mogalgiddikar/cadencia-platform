import { http, HttpResponse } from 'msw';

export const walletHandlers = [
  http.get('*/v1/wallet/challenge', () => HttpResponse.json({
    status: 'success',
    data: {
      challenge: 'Sign this message to verify wallet ownership: cadencia-nonce-abc123',
      enterprise_id: 'ent-001',
      expires_at: new Date(Date.now() + 300_000).toISOString(),
    },
  })),

  http.post('*/v1/wallet/link', () => HttpResponse.json({
    status: 'success',
    data: {
      algorand_address: 'MOCK7WALLET7ADDRESS7FOR7TESTING7PURPOSES7ALGO',
      message: 'Wallet linked successfully',
    },
  })),

  http.delete('*/v1/wallet/link', () => HttpResponse.json({
    status: 'success',
    data: { message: 'Wallet unlinked successfully' },
  })),

  http.get('*/v1/wallet/balance', () => HttpResponse.json({
    status: 'success',
    data: {
      algorand_address: 'MOCK7WALLET7ADDRESS7FOR7TESTING7PURPOSES7ALGO',
      algo_balance_microalgo: 125500000,
      algo_balance_algo: '125.5',
      min_balance: 100000,
      available_balance: 125400000,
      opted_in_apps: [
        { app_id: 12345678, app_name: 'Cadencia Escrow' },
      ],
    },
  })),
];
