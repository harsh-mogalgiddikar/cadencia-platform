import { http, HttpResponse } from 'msw';

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
        user: {
          id: 'user-001',
          email: body.user.email,
          full_name: body.user.full_name,
          role: 'ADMIN',
          enterprise_id: 'ent-001',
        },
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
    HttpResponse.json({ status: 'success', data: { access_token: 'mock-refreshed-xyz', token_type: 'bearer' } })
  ),

  // Enterprise details
  http.get('*/v1/enterprises/:id', () =>
    HttpResponse.json({
      status: 'success',
      data: {
        id: 'ent-001', legal_name: 'Tata Steel Ltd', pan: 'ABCDE1234F',
        gstin: '27ABCDE1234F1ZP', trade_role: 'BUYER', kyc_status: 'ACTIVE',
        industry_vertical: 'Steel Manufacturing', geography: 'Maharashtra',
        commodities: ['HR Coil', 'Cold Rolled'], min_order_value: 100000,
        max_order_value: 50000000, algorand_wallet: null, agent_config: null,
      }
    })
  ),
];
