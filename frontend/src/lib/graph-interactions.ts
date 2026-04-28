import type { Core, NodeSingular, EdgeSingular } from 'cytoscape';
import { getConnectedNodeIds } from './neo4j-graph';
import type { Neo4jGraphEdge } from './neo4j-graph';

/**
 * Threshold in pixels for distinguishing between click and drag
 */
const CLICK_DRAG_THRESHOLD = 5;

/**
 * Debounce time after drag to prevent treating drag release as click
 */
const DRAG_DEBOUNCE_MS = 120;

/**
 * Interaction state tracker
 */
export interface InteractionState {
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  hoveredNodeId: string | null;
  draggedNodeId: string | null;
  isDragging: boolean;
  lastPointerDownPos: { x: number; y: number } | null;
  lastDragEndAt: number;
}

export const initialInteractionState: InteractionState = {
  selectedNodeId: null,
  selectedEdgeId: null,
  hoveredNodeId: null,
  draggedNodeId: null,
  isDragging: false,
  lastPointerDownPos: null,
  lastDragEndAt: 0,
};

/**
 * Calculate euclidean distance
 */
function distance(p1: { x: number; y: number }, p2: { x: number; y: number }): number {
  return Math.hypot(p2.x - p1.x, p2.y - p1.y);
}

/**
 * Check if movement between two points is considered a "click"
 */
export function isClickMovement(start: { x: number; y: number }, end: { x: number; y: number }): boolean {
  return distance(start, end) < CLICK_DRAG_THRESHOLD;
}

/**
 * Check if we should ignore a click due to recent drag
 */
export function isDraggingRecently(lastDragEndAt: number): boolean {
  return Date.now() - lastDragEndAt < DRAG_DEBOUNCE_MS;
}

/**
 * Graph interaction controller
 */
export class GraphInteractionController {
  private cy: Core;
  private state: InteractionState;
  private stateUpdater: (state: InteractionState) => void;
  private edges: Neo4jGraphEdge[];

  constructor(
    cy: Core,
    edges: Neo4jGraphEdge[],
    initialState: InteractionState,
    stateUpdater: (state: InteractionState) => void
  ) {
    this.cy = cy;
    this.edges = edges;
    this.state = { ...initialState };
    this.stateUpdater = stateUpdater;
  }

  /**
   * Update state and notify listeners
   */
  private updateState(patch: Partial<InteractionState>) {
    this.state = { ...this.state, ...patch };
    this.stateUpdater(this.state);
  }

  /**
   * Handle node click
   */
  nodeClicked(node: NodeSingular) {
    // Ignore if this was actually a drag
    if (isDraggingRecently(this.state.lastDragEndAt)) {
      return;
    }

    const nodeId = node.id();
    const isAlreadySelected = this.state.selectedNodeId === nodeId;

    // Toggle selection
    if (isAlreadySelected) {
      this.clearSelection();
    } else {
      this.selectNode(nodeId);
    }
  }

  /**
   * Handle edge click
   */
  edgeClicked(edge: EdgeSingular) {
    if (isDraggingRecently(this.state.lastDragEndAt)) {
      return;
    }

    const edgeId = edge.id();
    const isAlreadySelected = this.state.selectedEdgeId === edgeId;

    if (isAlreadySelected) {
      this.clearSelection();
    } else {
      this.selectEdge(edgeId);
    }
  }

  /**
   * Handle canvas click (clear selection)
   */
  canvasClicked() {
    this.clearSelection();
  }

  /**
   * Handle node grab/drag start
   */
  nodeGrabStarted(node: NodeSingular, event: any) {
    this.updateState({
      draggedNodeId: node.id(),
      isDragging: false,
      lastPointerDownPos: { x: event.pageX, y: event.pageY },
    });
  }

  /**
   * Handle node drag (movement)
   */
  nodeDragging(node: NodeSingular, event: any) {
    const currentPos = { x: event.pageX, y: event.pageY };

    if (!this.state.lastPointerDownPos) {
      return;
    }

    const hasMoved = !isClickMovement(this.state.lastPointerDownPos, currentPos);

    if (hasMoved && !this.state.isDragging) {
      this.updateState({
        isDragging: true,
      });

      // Add visual feedback for dragging
      node.addClass('dragging');
    }
  }

  /**
   * Handle node release
   */
  nodeReleased(node: NodeSingular) {
    if (this.state.isDragging) {
      // Persist position
      this.updateState({
        lastDragEndAt: Date.now(),
      });
    }

    node.removeClass('dragging');

    this.updateState({
      draggedNodeId: null,
      isDragging: false,
      lastPointerDownPos: null,
    });
  }

  /**
   * Handle node hover
   */
  nodeHovered(node: NodeSingular) {
    this.updateState({
      hoveredNodeId: node.id(),
    });
  }

  /**
   * Handle node unhover
   */
  nodeUnhovered() {
    this.updateState({
      hoveredNodeId: null,
    });
  }

  /**
   * Select a node and highlight its neighborhood
   */
  selectNode(nodeId: string) {
    const node = this.cy.getElementById(nodeId);

    if (!node || node.isEdge()) {
      return;
    }

    // Clear previous selection
    (this.cy.$('node.selected') as any).removeClass('selected');
    (this.cy.$('edge.selected') as any).removeClass('selected');

    // Select the node
    (node as any).addClass('selected');
    this.updateState({
      selectedNodeId: nodeId,
      selectedEdgeId: null,
    });

    // Highlight neighborhood
    this.highlightNeighborhood(nodeId);
  }

  /**
   * Select an edge
   */
  selectEdge(edgeId: string) {
    const edge = this.cy.getElementById(edgeId) as any;

    if (!edge || edge.isNode?.()) {
      return;
    }

    // Clear previous selection
    (this.cy.$('node.selected') as any).removeClass('selected');
    (this.cy.$('edge.selected') as any).removeClass('selected');

    // Select the edge
    edge.addClass('selected');
    this.updateState({
      selectedEdgeId: edgeId,
      selectedNodeId: null,
    });

    // Highlight connected nodes
    const source = edge.source?.();
    const target = edge.target?.();

    (this.cy.$('node') as any).addClass('faded');
    (source as any)?.removeClass('faded').addClass('highlighted');
    (target as any)?.removeClass('faded').addClass('highlighted');

    (this.cy.$('edge') as any).addClass('faded');
    edge.removeClass('faded').addClass('highlighted');
  }

  /**
   * Clear selection
   */
  clearSelection() {
    (this.cy.$('node') as any).removeClass('selected highlighted faded');
    (this.cy.$('edge') as any).removeClass('selected highlighted faded');

    this.updateState({
      selectedNodeId: null,
      selectedEdgeId: null,
    });
  }

  /**
   * Highlight neighborhood of a node
   */
  private highlightNeighborhood(nodeId: string) {
    const connectedIds = getConnectedNodeIds(nodeId, this.edges);

    (this.cy.$('node') as any).forEach((node: any) => {
      if (connectedIds.has(node.id())) {
        node.removeClass('faded').addClass('highlighted');
      } else {
        node.removeClass('highlighted').addClass('faded');
      }
    });

    (this.cy.$('edge') as any).forEach((edge: any) => {
      const source = edge.source().id();
      const target = edge.target().id();

      if (connectedIds.has(source) && connectedIds.has(target)) {
        edge.removeClass('faded').addClass('highlighted');
      } else {
        edge.removeClass('highlighted').addClass('faded');
      }
    });
  }

  /**
   * Get current state
   */
  getState(): InteractionState {
    return { ...this.state };
  }

  /**
   * Update edges (for when graph data changes)
   */
  updateEdges(edges: Neo4jGraphEdge[]) {
    this.edges = edges;
  }
}
