import { http, HttpResponse } from 'msw';

export const sellerProfileHandlers = [
  // GET seller profile
  http.get('*/v1/marketplace/capability-profile', () => HttpResponse.json({
    status: 'success',
    data: {
      industry: 'Steel Manufacturing',
      geographies: ['Maharashtra', 'Gujarat', 'Karnataka'],
      products: ['HR Coil', 'Cold Rolled', 'Wire Rod'],
      min_order_value: 100000,
      max_order_value: 50000000,
      description: 'Leading HR Coil manufacturer with 2MT/day capacity. ISO 9001 certified. Pan-India delivery within 30 days. Competitive bulk pricing.',
      embedding_status: 'active',
      last_embedded: '2026-04-03T20:00:00Z',
    },
  })),

  // PUT update profile
  http.put('*/v1/marketplace/capability-profile', () => HttpResponse.json({
    status: 'success',
    data: {
      message: 'Seller profile updated successfully',
      embedding_status: 'queued',
    },
  })),

  // POST trigger embeddings
  http.post('*/v1/marketplace/capability-profile/embeddings', () => HttpResponse.json({
    status: 'success',
    data: {
      message: 'Embeddings recomputation queued. Profile will be active for matching in ~30 seconds.',
    },
  })),
];
