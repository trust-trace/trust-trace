'use client';

import { useEffect, useState } from 'react';

export function MswProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(process.env.NODE_ENV !== 'development');

  useEffect(() => {
    if (process.env.NODE_ENV !== 'development') {
      return;
    }

    let active = true;

    async function enableMocking() {
      const { worker } = await import('@/mocks/browser');

      await worker.start({ onUnhandledRequest: 'bypass' });

      if (active) {
        setReady(true);
      }
    }

    enableMocking();

    return () => {
      active = false;
    };
  }, []);

  if (!ready) {
    return null;
  }

  return <>{children}</>;
}
