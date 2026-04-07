import { useEffect, useRef } from 'react';
import { getAccessToken } from '@/lib/api';

// Full implementation in Phase 7 (Negotiation Live Room)
export function useSSE(_sessionId: string, _onEvent: (event: string, data: unknown) => void) {
  const readerRef = useRef<ReadableStreamDefaultReader | null>(null);

  useEffect(() => {
    return () => {
      readerRef.current?.cancel();
    };
  }, []);

  return { isConnected: false };
}
