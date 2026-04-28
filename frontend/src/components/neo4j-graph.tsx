'use client';

import { useEffect, useState } from 'react';

import { getNeo4jGraph } from '@/lib/api';
import { type Neo4jGraphPayload } from '@/lib/neo4j-graph';
import { CytoscapeGraph } from './cytoscape-graph';

type GraphStatus = 'loading' | 'error' | 'success';

export function Neo4jGraph() {
  const [status, setStatus] = useState<GraphStatus>('loading');
  const [graph, setGraph] = useState<Neo4jGraphPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getNeo4jGraph()
      .then((payload) => {
        if (cancelled) return;
        setGraph(payload);
        setStatus('success');
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setStatus('error');
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Neo4jGraphView
      status={status}
      graph={graph}
      error={error}
      selectedNodeId={selectedNodeId}
      selectedEdgeId={selectedEdgeId}
      onNodeSelected={setSelectedNodeId}
      onEdgeSelected={setSelectedEdgeId}
    />
  );
}

interface Neo4jGraphViewProps {
  status: GraphStatus;
  graph: Neo4jGraphPayload | null;
  error: string | null;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  onNodeSelected?: (nodeId: string | null) => void;
  onEdgeSelected?: (edgeId: string | null) => void;
}

export function Neo4jGraphView({
  status,
  graph,
  error,
  selectedNodeId,
  selectedEdgeId,
  onNodeSelected,
  onEdgeSelected,
}: Neo4jGraphViewProps) {
  if (status === 'loading') {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-empty">Ładowanie grafu...</div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-empty">Nie udało się załadować grafu: {error}</div>
      </div>
    );
  }

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="tt-graph-shell tt-graph-empty-state">
        <div className="tt-empty">Brak danych grafowych w Neo4j.</div>
      </div>
    );
  }

  return (
    <div className="tt-graph-shell">
      <CytoscapeGraph
        graph={graph}
        onNodeSelected={onNodeSelected}
        onEdgeSelected={onEdgeSelected}
      />
      {(selectedNodeId || selectedEdgeId) && (
        <div className="tt-graph-selection-info" style={{ padding: '8px', fontSize: '12px', color: '#666' }}>
          {selectedNodeId && `Selected: ${selectedNodeId}`}
          {selectedEdgeId && `Selected: ${selectedEdgeId}`}
        </div>
      )}
    </div>
  );
}
