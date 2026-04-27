'use client';

import { useState } from 'react';
import { COMPANIES, ARTICLES } from '@/lib/data';
import { Topbar } from '@/components/topbar';
import { Sidebar } from '@/components/sidebar';
import { MainPanel } from '@/components/main-panel';

export default function Home() {
  const [selectedId, setSelectedId] = useState('jsw');

  const company = COMPANIES.find((c) => c.id === selectedId) ?? COMPANIES[0];
  const articles = ARTICLES[company.id] ?? [];

  return (
    <div className="tt-root">
      <Topbar />
      <div className="tt-app-body">
        <Sidebar
          companies={COMPANIES}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        <MainPanel company={company} articles={articles} />
      </div>
    </div>
  );
}
