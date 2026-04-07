import { http, HttpResponse } from 'msw';

const MOCK_USER = {
  id: 'user-001',
  email: 'admin@tatasteel.com',
  full_name: 'Ravi Kumar',
  role: 'ADMIN',
  enterprise_id: 'ent-001',
};

const MOCK_ENTERPRISE = {
  id: 'ent-001',
  legal_name: 'Tata Steel Ltd',
  pan: 'ABCDE1234F',
  gstin: '27ABCDE1234F1ZP',
  trade_role: 'BUYER',
  kyc_status: 'ACTIVE',
  industry_vertical: 'Steel Manufacturing',
  geography: 'Maharashtra',
  commodities: ['HR Coil', 'Cold Rolled'],
  min_order_value: 100000,
  max_order_value: 50000000,
  algorand_wallet: null,
  agent_config: null,
};

export const authHandlers = [
  // Registration success
  http.post('*/v1/auth/register', async ({ request }) => {
    const body = await request.json() as any;
    return HttpResponse.json({
      status: 'success',
      data: {
        access_token: 'mock-token-registered-abc',
        token_type: 'bearer',
        enterprise_id: 'ent-001',
        user_id: 'user-001',
      },
    });
  }),

  // Login success
  http.post('*/v1/auth/login', async ({ request }) => {
    const body = await request.json() as any;
    if (body.email === 'admin@tatasteel.com' && body.password === 'password123') {
      return HttpResponse.json({
        status: 'success',
        data: {
          access_token: 'mock-token-login-xyz',
          token_type: 'bearer',
          enterprise_id: 'ent-001',
          user_id: 'user-001',
        },
      });
    }
    return HttpResponse.json(
      { status: 'error', detail: 'Invalid email or password' },
      { status: 401 }
    );
  }),

  // Token refresh
  http.post('*/v1/auth/refresh', () =>
    HttpResponse.json({
      status: 'success',
      data: { access_token: 'mock-refreshed-xyz', token_type: 'bearer' },
    })
  ),

  // GET /v1/auth/me — user profile
  http.get('*/v1/auth/me', () =>
    HttpResponse.json({
      status: 'success',
      data: MOCK_USER,
    })
  ),

  // Enterprise details
  http.get('*/v1/enterprises/:id', () =>
    HttpResponse.json({
      status: 'success',
      data: MOCK_ENTERPRISE,
    })
  ),
];
