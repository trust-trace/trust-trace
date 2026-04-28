import { getNodeColor, getNodeSize } from './cytoscape-adapter';

/**
 * Cytoscape stylesheet configuration
 */
export function getCytoscapeStylesheet(): any[] {
  return [
    {
      selector: 'node',
      css: {
        'background-color': (ele: any) => getNodeColor(ele.data('kind')),
        'content': 'data(label)',
        'text-valign': 'center',
        'text-halign': 'center',
        'text-wrap': 'wrap',
        'font-size': '11px',
        'color': '#fff',
        'font-weight': 'bold',
        'padding': '4px',
        'text-max-width': '80px',
        'width': (ele: any) => `${getNodeSize(ele.data('kind'))}px`,
        'height': (ele: any) => `${getNodeSize(ele.data('kind'))}px`,
        'border-width': '2px',
        'border-color': '#ffffff',
      },
    },
    {
      selector: 'node:selected',
      css: {
        'border-width': '3px',
        'border-color': '#ffcc00',
        'box-shadow': '0 0 10px rgba(255, 204, 0, 0.5)',
      },
    },
    {
      selector: 'node.highlighted',
      css: {
        'opacity': 1,
      },
    },
    {
      selector: 'node.faded',
      css: {
        'opacity': 0.3,
      },
    },
    {
      selector: 'node.dragging',
      css: {
        'z-index': 9999,
        'box-shadow': '0 0 15px rgba(0, 0, 0, 0.3)',
      },
    },
    {
      selector: 'edge',
      css: {
        'line-color': '#999999',
        'source-arrow-color': '#999999',
        'target-arrow-color': '#999999',
        'source-arrow-shape': 'none',
        'target-arrow-shape': 'triangle',
        'width': '2px',
        'content': 'data(label)',
        'font-size': '10px',
        'text-background-color': '#ffffff',
        'text-background-opacity': '0.8',
        'text-background-padding': '2px',
        'curve-style': 'bezier',
        'text-rotation': 'autorotate',
      },
    },
    {
      selector: 'edge:selected',
      css: {
        'line-color': '#ffcc00',
        'source-arrow-color': '#ffcc00',
        'target-arrow-color': '#ffcc00',
        'width': '3px',
      },
    },
    {
      selector: 'edge.highlighted',
      css: {
        'opacity': 1,
        'line-color': '#ffaa00',
      },
    },
    {
      selector: 'edge.faded',
      css: {
        'opacity': 0.2,
      },
    },
  ];
}

/**
 * Layout configuration for Cytoscape
 */
export const CYTOSCAPE_LAYOUT_CONFIG = {
  name: 'fcose',
  animate: true,
  animationDuration: 500,
  fit: true,
  padding: 40,
  nodeSeparation: 10,
  nodeRepulsion: 4500,
  edgeElasticity: 0.45,
  nungDragStarted: false,
  numIter: 2500,
  tiling: false,
  tilingPaddingVertical: 10,
  tilingPaddingHorizontal: 10,
  gravityRange: 240,
  gravity: 0.25,
  initialEnergyOnIncremental: 0.3,
};

export const FALLBACK_LAYOUT_CONFIG = {
  name: 'cose',
  animate: true,
  animationDuration: 500,
  fit: true,
  padding: 40,
  nodeSpacing: 10,
  nodeRepulsion: 4500,
  edgeElasticity: 0.45,
  numIter: 1000,
};
