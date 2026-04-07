import { http, HttpResponse } from 'msw';

export const adminHandlers = [
  // Platform stats
  http.get('*/v1/admin/stats', () => HttpResponse.json({
    status: 'success',
    data: {
      total_enterprises: 48,
      active_enterprises: 31,
      total_users: 124,
      active_sessions: 7,
      total_escrow_value: 284000000,
      pending_kyc: 6,
      llm_calls_today: 842,
      avg_negotiation_rounds: 11.4,
      success_rate: 73.2,
    },
  })),

  // All enterprises
  http.get('*/v1/admin/enterprises', () => HttpResponse.json({
    status: 'success',
    data: [
      { id: 'ent-001', legal_name: 'Tata Steel Ltd', kyc_status: 'ACTIVE', trade_role: 'BUYER', user_count: 12, created_at: '2026-01-10T09:00Z' },
      { id: 'ent-002', legal_name: 'JSW Steel Ltd', kyc_status: 'PENDING', trade_role: 'SELLER', user_count: 8, created_at: '2026-01-15T10:00Z' },
      { id: 'ent-003', legal_name: 'SAIL Corp', kyc_status: 'ACTIVE', trade_role: 'BOTH', user_count: 15, created_at: '2026-01-20T11:00Z' },
      { id: 'ent-004', legal_name: 'Hindalco Ltd', kyc_status: 'REJECTED', trade_role: 'BUYER', user_count: 5, created_at: '2026-02-01T09:00Z' },
      { id: 'ent-005', legal_name: 'Arcelor Mittal India', kyc_status: 'PENDING', trade_role: 'SELLER', user_count: 9, created_at: '2026-02-10T12:00Z' },
    ],
  })),

  // KYC approval/rejection
  http.patch('*/v1/admin/enterprises/:id/kyc', async ({ request, params }) => {
    const body = await request.json() as { action: 'approve' | 'reject' | 'revoke' };
    return HttpResponse.json({
      status: 'success',
      data: {
        id: params.id,
        kyc_status: body.action === 'approve' ? 'ACTIVE' : body.action === 'reject' ? 'REJECTED' : 'NOT_SUBMITTED',
        message: `KYC action applied for enterprise ${params.id}`,
      },
    });
  }),

  // All users
  http.get('*/v1/admin/users', () => HttpResponse.json({
    status: 'success',
    data: [
      { id: 'user-001', full_name: 'Ratan Tata', email: 'ratan@tata.com', role: 'ADMIN', enterprise_id: 'ent-001', enterprise_name: 'Tata Steel Ltd', status: 'ACTIVE', last_login: '2026-04-03T20:00Z' },
      { id: 'user-002', full_name: 'Sajjan Jindal', email: 'sajjan@jsw.com', role: 'MEMBER', enterprise_id: 'ent-002', enterprise_name: 'JSW Steel Ltd', status: 'ACTIVE', last_login: '2026-04-02T14:00Z' },
      { id: 'user-003', full_name: 'Anil Verma', email: 'anil@sail.com', role: 'ADMIN', enterprise_id: 'ent-003', enterprise_name: 'SAIL Corp', status: 'SUSPENDED', last_login: '2026-03-20T10:00Z' },
      { id: 'user-004', full_name: 'Priya Sharma', email: 'priya@hindalco.com', role: 'MEMBER', enterprise_id: 'ent-004', enterprise_name: 'Hindalco Ltd', status: 'ACTIVE', last_login: '2026-04-01T09:00Z' },
    ],
  })),

  // Suspend user
  http.patch('*/v1/admin/users/:id/suspend', async ({ params, request }) => {
    const body = await request.json() as { action: 'suspend' | 'reinstate' };
    return HttpResponse.json({
      status: 'success',
      data: {
        id: params.id,
        status: body.action === 'suspend' ? 'SUSPENDED' : 'ACTIVE',
      },
    });
  }),

  // Active AI agents
  http.get('*/v1/admin/agents', () => HttpResponse.json({
    status: 'success',
    data: [
      { session_id: 'sess-001', status: 'RUNNING', current_round: 5, model: 'gemini-2.0-flash', latency_ms: 420, buyer: 'Tata Steel Ltd', seller: 'JSW Steel Ltd', started_at: '2026-04-01T12:00Z' },
      { session_id: 'sess-003', status: 'PAUSED', current_round: 8, model: 'gemini-2.0-flash', latency_ms: 0, buyer: 'Hindalco Ltd', seller: 'Tata Steel Ltd', started_at: '2026-03-30T14:00Z' },
    ],
  })),

  // Pause agent
  http.post('*/v1/admin/agents/:session_id/pause', ({ params }) => HttpResponse.json({
    status: 'success',
    data: { session_id: params.session_id, status: 'PAUSED' },
  })),

  // Resume agent
  http.post('*/v1/admin/agents/:session_id/resume', ({ params }) => HttpResponse.json({
    status: 'success',
    data: { session_id: params.session_id, status: 'RUNNING' },
  })),

  // LLM logs
  http.get('*/v1/admin/llm-logs', () => HttpResponse.json({
    status: 'success',
    data: [
      {
        id: 'llm-001',
        session_id: 'sess-001',
        round: 5,
        agent: 'BUYER',
        model: 'gemini-2.0-flash',
        prompt_tokens: 842,
        completion_tokens: 156,
        latency_ms: 420,
        status: 'SUCCESS',
        created_at: '2026-04-01T15:05Z',
        prompt_summary: 'Analyze offer of ₹41,500/MT vs budget range ₹38K-42K...',
        response_summary: 'Counter-offer ₹40,800/MT with FOB Mumbai terms...',
      },
      {
        id: 'llm-002',
        session_id: 'sess-001',
        round: 6,
        agent: 'SELLER',
        model: 'gemini-2.0-flash',
        prompt_tokens: 920,
        completion_tokens: 201,
        latency_ms: 380,
        status: 'SUCCESS',
        created_at: '2026-04-01T15:08Z',
        prompt_summary: 'Evaluate counter-offer ₹40,800/MT, margin analysis...',
        response_summary: 'Accept at ₹41,000/MT with revised payment terms...',
      },
      {
        id: 'llm-003',
        session_id: 'sess-003',
        round: 3,
        agent: 'BUYER',
        model: 'gemini-2.0-flash',
        prompt_tokens: 610,
        completion_tokens: 0,
        latency_ms: 8500,
        status: 'TIMEOUT',
        created_at: '2026-03-30T14:20Z',
        prompt_summary: 'Initial offer generation for Wire Rod...',
        response_summary: null,
      },
    ],
  })),

  // Platform broadcast
  http.post('*/v1/admin/broadcast', async ({ request }) => {
    const body = await request.json() as { target: string; priority: string; message: string };
    return HttpResponse.json({
      status: 'success',
      data: {
        message_id: `msg-${Date.now()}`,
        recipients: body.target === 'all' ? 124 : 31,
        delivered: true,
      },
    });
  }),
];
