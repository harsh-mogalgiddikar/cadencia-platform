import { http, HttpResponse } from 'msw';

const ALL_ESCROWS = [
  {
    escrow_id: 'escrow-001', session_id: 'sess-001',
    algo_app_id: 12345678, algo_app_address: 'ALGO-APP-ADDR-001',
    amount_microalgo: 20100000000, amount_algo: 20.1,
    status: 'FUNDED', frozen: false,
    deploy_tx_id: 'ALGO-TX-DEPLOY-001', fund_tx_id: 'ALGO-TX-FUND-001',
    release_tx_id: null, refund_tx_id: null, merkle_root: null,
    buyer_name: 'Tata Steel Ltd', seller_name: 'JSW Steel Ltd',
    created_at: '2026-04-01T15:00:00Z', settled_at: null,
  },
  {
    escrow_id: 'escrow-002', session_id: 'sess-002',
    algo_app_id: 87654321, algo_app_address: 'ALGO-APP-ADDR-002',
    amount_microalgo: 4050000000, amount_algo: 4.05,
    status: 'RELEASED', frozen: false,
    deploy_tx_id: 'ALGO-TX-DEPLOY-002', fund_tx_id: 'ALGO-TX-FUND-002',
    release_tx_id: 'ALGO-TX-RELEASE-002', refund_tx_id: null, merkle_root: 'abc123def456',
    buyer_name: 'Tata Steel Ltd', seller_name: 'SAIL Corp',
    created_at: '2026-03-31T16:00:00Z', settled_at: '2026-04-01T10:00:00Z',
  },
  {
    escrow_id: 'escrow-003', session_id: 'sess-003',
    algo_app_id: null, algo_app_address: null,
    amount_microalgo: 12500000000, amount_algo: 12.5,
    status: 'DEPLOYED', frozen: false,
    deploy_tx_id: 'ALGO-TX-DEPLOY-003', fund_tx_id: null,
    release_tx_id: null, refund_tx_id: null, merkle_root: null,
    buyer_name: 'Hindalco Ltd', seller_name: 'Tata Steel Ltd',
    created_at: '2026-03-30T17:00:00Z', settled_at: null,
  },
];

export const escrowHandlers = [
  // GET list escrows
  http.get('*/v1/escrow', ({ request }) => {
    const url = new URL(request.url);
    const statusFilter = url.searchParams.get('status');
    let filtered = ALL_ESCROWS;
    if (statusFilter) {
      filtered = filtered.filter(e => e.status === statusFilter);
    }
    return HttpResponse.json({ status: 'success', data: filtered });
  }),

  // GET escrow by session
  http.get('*/v1/escrow/:session_id', ({ params }) => {
    const escrow = ALL_ESCROWS.find(e => e.session_id === params.session_id);
    return HttpResponse.json({
      status: 'success',
      data: escrow ?? { status: 'NOT_DEPLOYED' },
    });
  }),

  // Deploy contract
  http.post('*/v1/escrow/:session_id/deploy', () => HttpResponse.json({
    status: 'success',
    data: {
      escrow_id: `escrow-${Date.now()}`,
      algo_app_id: 12345678 + Math.floor(Math.random() * 1000),
      algo_app_address: 'ALGO-APP-ADDR-NEW',
      status: 'DEPLOYED',
      tx_id: `ALGO-TX-DEPLOY-${Date.now()}`,
    },
  })),

  // Fund escrow
  http.post('*/v1/escrow/:escrow_id/fund', () => HttpResponse.json({
    status: 'success',
    data: { status: 'FUNDED', tx_id: 'ALGO-TX-FUND-LEGACY-XYZ' },
  })),

  // Release
  http.post('*/v1/escrow/:escrow_id/release', () => HttpResponse.json({
    status: 'success',
    data: { status: 'RELEASED', tx_id: 'ALGO-TX-RELEASE-ABC' },
  })),

  // Refund
  http.post('*/v1/escrow/:escrow_id/refund', () => HttpResponse.json({
    status: 'success',
    data: { status: 'REFUNDED', tx_id: 'ALGO-TX-REFUND-DEF' },
  })),

  // Freeze
  http.post('*/v1/escrow/:escrow_id/freeze', () => HttpResponse.json({
    status: 'success',
    data: { status: 'FROZEN', message: 'Escrow frozen pending dispute resolution' },
  })),

  // Settlements history
  http.get('*/v1/escrow/:escrow_id/settlements', () => HttpResponse.json({
    status: 'success',
    data: [
      { settlement_id: 'settle-001', escrow_id: 'escrow-001', milestone_index: 0, amount_microalgo: 20100000000, tx_id: 'ALGO-TX-FUND-XYZ', settled_at: '2026-04-01T15:05:00Z' },
      { settlement_id: 'settle-002', escrow_id: 'escrow-001', milestone_index: 1, amount_microalgo: 20100000000, tx_id: 'ALGO-TX-RELEASE-ABC', settled_at: '2026-04-02T10:30:00Z' },
    ],
  })),

  // Build Pera funding transactions
  http.get('*/v1/escrow/:escrow_id/build-fund-txn', () => HttpResponse.json({
    status: 'success',
    data: {
      unsigned_transactions: ['base64-encoded-payment-txn', 'base64-encoded-appcall-fund-txn'],
      group_id: 'base64-group-id-g123456789',
      transaction_count: 2,
      description: 'Atomic group: PaymentTxn → EscrowApp.fund()',
    },
  })),

  // Submit signed Pera transactions
  http.post('*/v1/escrow/:escrow_id/submit-signed-fund', () => HttpResponse.json({
    status: 'success',
    data: { txid: 'ALGO-TX-PERA-FUND-123456', confirmed_round: 23456789 },
  })),
];
