import { http, HttpResponse } from 'msw';

export const enterpriseHandlers = [
  // PATCH KYC
  http.patch('*/v1/enterprises/:enterprise_id/kyc', () =>
    HttpResponse.json({
      status: 'success',
      data: { kyc_status: 'PENDING', message: 'KYC documents submitted for review' },
    })
  ),

  // PUT agent config
  http.put('*/v1/enterprises/:enterprise_id/agent-config', () =>
    HttpResponse.json({
      status: 'success',
      data: { message: 'Agent configuration updated successfully' },
    })
  ),
];
