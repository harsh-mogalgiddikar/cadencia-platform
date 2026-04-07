'use client';

import { useState, useEffect } from 'react';

const ENABLE_MOCKS = process.env.NEXT_PUBLIC_ENABLE_MOCKS === 'true';

export function MSWProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (ENABLE_MOCKS) {
      import('@/mocks/browser').then(({ worker }) => {
        worker.start({ onUnhandledRequest: 'bypass' }).then(() => {
          setReady(true);
        });
      });
    } else {
      // In production or when mocks disabled — render immediately
      setReady(true);
    }
  }, []);

  if (!ready) return null;

  return <>{children}</>;
}
