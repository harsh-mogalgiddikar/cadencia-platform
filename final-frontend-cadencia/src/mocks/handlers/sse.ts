import { http, HttpResponse } from 'msw';

export const sseHandlers = [
  // SSE stream
  http.get('*/v1/sessions/:session_id/stream', () => {
    const events = [
      'event: new_offer\ndata: {"offer":{"round":6,"agent":"SELLER","price":41500,"currency":"INR","terms":{"delivery":"FOB Mumbai","payment":"LC at sight"},"confidence":82,"created_at":"2026-04-03T12:06:00Z"}}\n\n',
      'event: new_offer\ndata: {"offer":{"round":7,"agent":"BUYER","price":40800,"currency":"INR","terms":{"delivery":"FOB Mumbai","payment":"Advance 30%"},"confidence":75,"created_at":"2026-04-03T12:07:00Z"}}\n\n',
      'event: stall_detected\ndata: {"stall_round":8}\n\n',
      'event: new_offer\ndata: {"offer":{"round":8,"agent":"SELLER","price":41200,"currency":"INR","terms":{"delivery":"CIF Mumbai","payment":"LC at sight"},"confidence":78,"created_at":"2026-04-03T12:08:00Z"}}\n\n',
      'event: new_offer\ndata: {"offer":{"round":9,"agent":"BUYER","price":41000,"currency":"INR","terms":{"delivery":"CIF Mumbai","payment":"LC 60 days"},"confidence":85,"created_at":"2026-04-03T12:09:00Z"}}\n\n',
    ];

    const stream = new ReadableStream({
      start(controller) {
        let index = 0;
        const interval = setInterval(() => {
          if (index < events.length) {
            controller.enqueue(new TextEncoder().encode(events[index]));
            index++;
          } else {
            clearInterval(interval);
            controller.close();
          }
        }, 2500);
      },
    });

    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  }),

  // POST next turn
  http.post('*/v1/sessions/:session_id/turn', () => HttpResponse.json({
    status: 'success',
    data: { message: 'Next turn triggered. SSE stream will deliver the offer.' },
  })),

  // POST human override
  http.post('*/v1/sessions/:session_id/override', () => HttpResponse.json({
    status: 'success',
    data: { message: 'Human override submitted. SSE stream will continue.' },
  })),
];
