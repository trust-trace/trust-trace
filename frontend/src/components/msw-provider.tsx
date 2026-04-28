'use client';

import { useEffect, useState } from 'react';

export function MswProvider({ children }: { children: React.ReactNode }) {
  const shouldMock =
    process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_ENABLE_MSW === 'true';
  const [ready, setReady] = useState(!shouldMock);

  useEffect(() => {
    if (!shouldMock) {
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
  }, [shouldMock]);

  if (!ready) {
    return null;
  }

  return <>{children}</>;
}
