import { http, HttpResponse } from 'msw';

const ALL_RFQS = [
  {
    id: 'rfq-001',
    raw_text: 'Need 500 metric tons of HR Coil, IS 2062 grade, delivery to Mumbai port within 45 days. Budget: ₹38,000-42,000 per MT.',
    status: 'MATCHED',
    parsed_fields: { product: 'HR Coil', hsn: '72083990', quantity: '500 MT', budget_min: '38000', budget_max: '42000', delivery_days: '45', geography: 'Mumbai' },
    created_at: '2026-03-28T10:00:00Z',
  },
  {
    id: 'rfq-002',
    raw_text: '200MT Cold Rolled Steel, Maharashtra, 30 days delivery.',
    status: 'PARSED',
    parsed_fields: { product: 'Cold Rolled Steel', quantity: '200 MT', geography: 'Maharashtra', delivery_days: '30' },
    created_at: '2026-03-29T11:00:00Z',
  },
  {
    id: 'rfq-003',
    raw_text: '100MT Wire Rod, Gujarat delivery, urgent.',
    status: 'CONFIRMED',
    parsed_fields: { product: 'Wire Rod', quantity: '100 MT', geography: 'Gujarat' },
    created_at: '2026-03-30T09:00:00Z',
  },
];

export const marketplaceHandlers = [
  // GET list RFQs
  http.get('*/v1/marketplace/rfqs', () => HttpResponse.json({
    status: 'success',
    data: ALL_RFQS,
  })),

  // POST new RFQ
  http.post('*/v1/marketplace/rfq', () => HttpResponse.json({
    status: 'success',
    data: {
      rfq_id: 'rfq-004',
      status: 'DRAFT',
      message: 'RFQ submitted for processing. You will be notified when parsing completes.',
    },
  }, { status: 202 })),

  // GET RFQ details
  http.get('*/v1/marketplace/rfq/:rfq_id', ({ params }) => {
    const rfqs: Record<string, object> = {
      'rfq-001': {
        id: 'rfq-001',
        raw_text: 'Need 500 metric tons of HR Coil, IS 2062 grade, delivery to Mumbai port within 45 days. Budget: ₹38,000-42,000 per MT.',
        status: 'MATCHED',
        parsed_fields: {
          product: 'HR Coil',
          hsn: '72083990',
          quantity: '500 MT',
          budget_min: '38000',
          budget_max: '42000',
          delivery_days: '45',
          geography: 'Mumbai',
        },
        created_at: '2026-03-28T10:00:00Z',
      },
      'rfq-002': {
        id: 'rfq-002',
        raw_text: '200MT Cold Rolled Steel, Maharashtra, 30 days delivery.',
        status: 'PARSED',
        parsed_fields: {
          product: 'Cold Rolled Steel',
          quantity: '200 MT',
          geography: 'Maharashtra',
          delivery_days: '30',
        },
        created_at: '2026-03-29T11:00:00Z',
      },
      'rfq-003': {
        id: 'rfq-003',
        raw_text: '100MT Wire Rod, Gujarat delivery, urgent.',
        status: 'CONFIRMED',
        parsed_fields: { product: 'Wire Rod', quantity: '100 MT', geography: 'Gujarat' },
        created_at: '2026-03-30T09:00:00Z',
      },
      'rfq-004': {
        id: 'rfq-004',
        raw_text: 'New RFQ test',
        status: 'PARSED',
        parsed_fields: { product: 'Test Product', quantity: '100 MT' },
        created_at: new Date().toISOString(),
      },
    };
    const rfq = rfqs[params.rfq_id as string];
    if (!rfq) return HttpResponse.json({ status: 'error', detail: 'Not found' }, { status: 404 });
    return HttpResponse.json({ status: 'success', data: rfq });
  }),

  // GET RFQ matches
  http.get('*/v1/marketplace/rfq/:rfq_id/matches', ({ params }) => {
    if (params.rfq_id !== 'rfq-001') {
      return HttpResponse.json({ status: 'success', data: [] });
    }
    return HttpResponse.json({
      status: 'success',
      data: [
        {
          enterprise_id: 'ent-002',
          enterprise_name: 'JSW Steel Ltd',
          score: 94.2,
          rank: 1,
          capabilities: ['HR Coil production', 'Pan-India delivery'],
        },
        {
          enterprise_id: 'ent-003',
          enterprise_name: 'SAIL Corp',
          score: 87.5,
          rank: 2,
          capabilities: ['Steel manufacturing', 'Mumbai logistics'],
        },
        {
          enterprise_id: 'ent-004',
          enterprise_name: 'Arcelor Mittal India',
          score: 81.3,
          rank: 3,
          capabilities: ['Hot rolled products', 'High volume'],
        },
      ],
    });
  }),

  // POST confirm match
  http.post('*/v1/marketplace/rfq/:rfq_id/confirm', () =>
    HttpResponse.json({
      status: 'success',
      data: {
        message: 'Negotiation session created with selected seller. Redirecting to negotiations...',
        session_id: 'sess-004',
      },
    })
  ),
];
