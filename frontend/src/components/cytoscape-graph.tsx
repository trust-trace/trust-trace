'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import type { Core } from 'cytoscape';

import type { Neo4jGraphPayload } from '@/lib/neo4j-graph';
import {
  normalizeNeo4jGraph,
  toCytoscapeElements,
} from '@/lib/cytoscape-adapter';
import {
  getCytoscapeStylesheet,
  CYTOSCAPE_LAYOUT_CONFIG,
  FALLBACK_LAYOUT_CONFIG,
} from '@/lib/cytoscape-styles';
import {
  GraphInteractionController,
  initialInteractionState,
  type InteractionState,
} from '@/lib/graph-interactions';

interface CytoscapeGraphProps {
  graph: Neo4jGraphPayload;
  onNodeSelected?: (nodeId: string | null) => void;
  onEdgeSelected?: (edgeId: string | null) => void;
}

export function CytoscapeGraph({
  graph,
  onNodeSelected,
  onEdgeSelected,
}: CytoscapeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const controllerRef = useRef<GraphInteractionController | null>(null);
  const [interactionState, setInteractionState] = useState<InteractionState>(initialInteractionState);

  // Initialize Cytoscape instance once
  useEffect(() => {
    let cancelled = false;

    async function initializeCytoscape() {
      // Dynamic import to avoid SSR issues
      const cytoscape = (await import('cytoscape')).default;
      const fcose = (await import('cytoscape-fcose')).default;

      if (cancelled || !containerRef.current) return;

      // Register layout extension
      cytoscape.use(fcose);

      // Normalize and convert data
      const normalized = normalizeNeo4jGraph(graph);
      const elements = toCytoscapeElements(normalized);

      // Create Cytoscape instance
      const cy = cytoscape({
        container: containerRef.current,
        elements,
        style: getCytoscapeStylesheet(),
        layout: CYTOSCAPE_LAYOUT_CONFIG as any,
        wheelSensitivity: 0.1,
        autoungrabify: false,
        boxSelectionEnabled: false,
        selectionType: 'single',
      });

      if (cancelled) return;

      cyRef.current = cy;

      // Initialize interaction controller
      const controller = new GraphInteractionController(
        cy,
        graph.edges,
        initialInteractionState,
        setInteractionState
      );
      controllerRef.current = controller;

      // Setup event listeners
      setupEventListeners(cy, controller);

      // Fit to view
      cy.fit(undefined, 40);
    }

    initializeCytoscape().catch(console.error);

    return () => {
      cancelled = true;
    };
  }, [graph, graph.edges]);

  // Update interaction state when callbacks change
  useEffect(() => {
    if (onNodeSelected) {
      onNodeSelected(interactionState.selectedNodeId);
    }
    if (onEdgeSelected) {
      onEdgeSelected(interactionState.selectedEdgeId);
    }
  }, [interactionState.selectedNodeId, interactionState.selectedEdgeId, onNodeSelected, onEdgeSelected]);

  return (
    <div
      ref={containerRef}
      className="tt-cytoscape-container"
      style={{
        width: '100%',
        height: '560px',
        minHeight: '560px',
        backgroundColor: '#ffffff',
        border: '1px solid var(--tt-border)',
        borderRadius: '8px',
        overflow: 'hidden',
      }}
    />
  );
}

/**
 * Setup all event listeners for Cytoscape
 */
function setupEventListeners(cy: Core, controller: GraphInteractionController) {
  // Node interactions
  cy.on('tap', 'node', (event) => {
    controller.nodeClicked(event.target);
  });

  cy.on('grab', 'node', (event) => {
    controller.nodeGrabStarted(event.target, event);
  });

  cy.on('drag', 'node', (event) => {
    controller.nodeDragging(event.target, event);
  });

  cy.on('free', 'node', (event) => {
    controller.nodeReleased(event.target);
  });

  cy.on('mouseover', 'node', (event) => {
    controller.nodeHovered(event.target);
  });

  cy.on('mouseout', 'node', (event) => {
    controller.nodeUnhovered();
  });

  // Edge interactions
  cy.on('tap', 'edge', (event) => {
    controller.edgeClicked(event.target);
  });

  // Canvas interactions
  cy.on('tap', (event) => {
    if (event.target === cy) {
      controller.canvasClicked();
    }
  });
}
