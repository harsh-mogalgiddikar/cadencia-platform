import { http, HttpResponse } from 'msw';

export const complianceHandlers = [
  // Audit log — cursor pagination (updated to match AuditEntry shape)
  http.get('*/v1/audit/:escrow_id', ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '20', 10);

    const entries = Array.from({ length: 12 }).map((_, i) => ({
      entry_id: `entry-${(i + 1).toString().padStart(3, '0')}`,
      escrow_id: url.pathname.split('/audit/')[1]?.split('?')[0] || 'escrow-001',
      sequence_no: i + 1,
      event_type: ['DEPLOYED', 'FUNDED', 'RELEASED', 'FROZEN', 'REFUNDED'][i % 5],
      payload_json: JSON.stringify({ actor: i % 2 === 0 ? 'buyer@tata.com' : 'smart_contract', tx_id: `ALGO-TX-${i}` }),
      prev_hash: i === 0 ? '0000000000000000' : `sha256-${Math.random().toString(36).substring(2, 18)}`,
      entry_hash: `sha256-${Math.random().toString(36).substring(2, 18)}`,
      created_at: new Date(Date.now() - i * 3600000).toISOString(),
    }));

    return HttpResponse.json({
      status: 'success',
      data: { entries, next_cursor: null },
    });
  }),

  // Verify chain
  http.get('*/v1/audit/:escrow_id/verify', () => HttpResponse.json({
    status: 'success',
    data: { valid: true, entry_count: 12, first_invalid_sequence_no: null },
  })),

  // FEMA record (matches FEMARecord type)
  http.get('*/v1/compliance/:escrow_id/fema', ({ params }) => HttpResponse.json({
    status: 'success',
    data: {
      record_id: 'fema-001',
      escrow_id: params.escrow_id,
      form_type: '15CA',
      purpose_code: 'P0103',
      buyer_pan: 'ABCDE1234F',
      seller_pan: 'FGHIJ5678K',
      amount_inr: 20100000,
      amount_algo: 20.1,
      fx_rate_inr_per_algo: 1000000,
      merkle_root: 'abc123def456789',
      generated_at: '2026-04-02T10:00:00Z',
    },
  })),

  // GST record (matches GSTRecord type)
  http.get('*/v1/compliance/:escrow_id/gst', ({ params }) => HttpResponse.json({
    status: 'success',
    data: {
      record_id: 'gst-001',
      escrow_id: params.escrow_id,
      hsn_code: '72083990',
      buyer_gstin: '27ABCDE1234F1ZP',
      seller_gstin: '27FGHIJ5678K1ZQ',
      tax_type: 'CGST_SGST',
      taxable_amount: 20100000,
      igst_amount: 0,
      cgst_amount: 1005000,
      sgst_amount: 1005000,
      total_tax: 2010000,
      generated_at: '2026-04-02T10:00:00Z',
    },
  })),

  // PDF download
  http.get('*/v1/compliance/:escrow_id/fema/pdf', ({ params }) =>
    HttpResponse.json({
      status: 'success',
      data: { download_url: `/mock/fema-${params.escrow_id}.pdf` },
    })
  ),

  // CSV download
  http.get('*/v1/compliance/:escrow_id/gst/csv', ({ params }) =>
    HttpResponse.json({
      status: 'success',
      data: { download_url: `/mock/gst-${params.escrow_id}.csv` },
    })
  ),

  // Bulk ZIP export
  http.post('*/v1/compliance/export/zip', () => HttpResponse.json({
    status: 'success',
    data: {
      job_id: `export-${Math.floor(Math.random() * 1000)}`,
      status: 'QUEUED',
      redis_key: null,
      error_message: null,
      created_at: new Date().toISOString(),
      completed_at: null,
    },
  })),
];
