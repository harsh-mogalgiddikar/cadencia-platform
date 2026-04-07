import { http, HttpResponse } from 'msw';

export const healthHandlers = [
  http.get('*/health', () =>
    HttpResponse.json({
      status: 'success',
      data: {
        overall: 'healthy',
        services: {
          database: 'healthy',
          redis: 'healthy',
          algorand: 'healthy',
          llm: 'healthy',
        },
        timestamp: new Date().toISOString(),
      },
    })
  ),
];
