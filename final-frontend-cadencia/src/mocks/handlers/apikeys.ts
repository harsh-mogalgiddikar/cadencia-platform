import { http, HttpResponse } from 'msw';

export const apikeysHandlers = [
  // GET api keys
  http.get('*/v1/auth/api-keys', () => HttpResponse.json({
    status: 'success',
    data: [
      {
        id: 'key-001',
        label: 'ERP System',
        created_at: '2026-03-01T10:00:00Z',
        last_used: '2026-04-02T14:30:00Z',
      },
      {
        id: 'key-002',
        label: 'Mobile App',
        created_at: '2026-03-15T09:00:00Z',
        last_used: null,
      },
    ],
  })),

  // POST create key
  http.post('*/v1/auth/api-keys', async ({ request }) => {
    const body = await request.json() as any;
    const key = `cad-${Math.random().toString(36).slice(2, 10)}-${Math.random().toString(36).slice(2, 6)}`;
    return HttpResponse.json({
      status: 'success',
      data: {
        id: `key-${Date.now()}`,
        label: body.label,
        key,
        created_at: new Date().toISOString(),
      },
    });
  }),

  // DELETE key
  http.delete('*/v1/auth/api-keys/:key_id', () =>
    HttpResponse.json({
      status: 'success',
      data: { message: 'API key revoked successfully' },
    })
  ),
];
