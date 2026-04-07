import { http, HttpResponse } from 'msw';

export const treasuryHandlers = [
  http.get('*/v1/treasury/dashboard', () => HttpResponse.json({
    status: 'success',
    data: {
      inr_pool_balance: '15000000',
      usdc_pool_balance: '180000',
      algo_pool_balance_microalgo: 500000000000,
      algo_pool_balance_algo: '500000',
      current_fx_rate: { INR_USD: '83.25', updated_at: '2026-04-07T10:00:00Z' },
      total_value_inr: '30000000',
      open_fx_positions: 3,
    },
  })),

  http.get('*/v1/treasury/fx-exposure', () => HttpResponse.json({
    status: 'success',
    data: {
      open_positions: [
        { position_id: 'pos-001', pair: 'INR/USD', direction: 'LONG', notional: '1000000', entry_rate: '82.50', current_rate: '83.25', unrealized_pnl: '9090' },
        { position_id: 'pos-002', pair: 'USDC/ALGO', direction: 'SHORT', notional: '50000', entry_rate: '0.15', current_rate: '0.14', unrealized_pnl: '500' },
      ],
      total_unrealized_pnl: '9590',
      position_count: 2,
    },
  })),

  http.get('*/v1/treasury/liquidity-forecast', () => HttpResponse.json({
    status: 'success',
    data: {
      forecast: Array.from({ length: 14 }, (_, i) => ({
        date: new Date(Date.now() + i * 86400000).toISOString().slice(0, 10),
        projected_inr_balance: String(15000000 - i * 200000),
        projected_usdc_balance: String(180000 - i * 3000),
      })),
      runway_days: 45,
      alert: null,
      current_inr_balance: '15000000',
      current_usdc_balance: '180000',
      estimated_daily_burn_inr: '333333',
    },
  })),
];
