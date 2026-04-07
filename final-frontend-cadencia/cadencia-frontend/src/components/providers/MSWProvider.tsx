'use client';

import { useState, useEffect } from 'react';

export function MSWProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      import('@/mocks/browser').then(({ worker }) => {
        worker.start({ onUnhandledRequest: 'bypass' }).then(() => {
          setReady(true);
        });
      });
    } else {
      // In production, MSW is not used — render immediately
      setReady(true);
    }
  }, []);

  if (!ready) return null;

  return <>{children}</>;
}
