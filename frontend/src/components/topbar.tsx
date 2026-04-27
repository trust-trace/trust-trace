'use client';

import { useState, useEffect } from 'react';

export function Topbar() {
  const [time, setTime] = useState('');

  useEffect(() => {
    function tick() {
      const d = new Date();
      setTime(
        `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
      );
    }
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="tt-topbar">
      <div className="tt-logo">
        <span className="tt-logo-mark">tt</span>
        <span>
          trust<span className="tt-logo-italic">·</span>
          <i>trace</i>
        </span>
      </div>
      <div className="tt-topbar-right">
        <span className="tt-pill">
          <span className="tt-live-dot" />
          Live · 38 źródeł
        </span>
        <span className="tt-mono" style={{ color: 'var(--tt-fg-mute)', fontSize: 11 }}>
          {time}
        </span>
        <div className="tt-avatar">MK</div>
      </div>
    </div>
  );
}
