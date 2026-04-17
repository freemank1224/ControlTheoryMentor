import { useEffect, useRef } from 'react';
import cytoscape, { Core, ElementDefinition } from 'cytoscape';
import type { GraphDataResponse } from '@/types/api';

interface KnowledgeGraphProps {
  data: GraphDataResponse;
  onNodeClick?: (nodeId: string) => void;
  highlightedNodes?: string[];
}

export function KnowledgeGraph({ data, onNodeClick, highlightedNodes = [] }: KnowledgeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!containerRef.current || !data) return;

    // Convert data format
    const elements: ElementDefinition[] = [
      ...data.elements.nodes.map(n => ({ data: n.data })),
      ...data.elements.edges.map(e => ({ data: e.data }))
    ];

    // Initialize Cytoscape
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#faf9f5',
            'border-color': '#c96442',
            'border-width': 2,
            'label': 'data(label)',
            'color': '#141413',
            'font-family': 'Inter, sans-serif',
            'font-size': '12px',
            'text-valign': 'center',
            'text-halign': 'center'
          }
        },
        {
          selector: 'node.highlighted',
          style: {
            'background-color': '#c96442',
            'border-color': '#141413'
          }
        },
        {
          selector: 'node.faded',
          style: {
            'opacity': 0.3
          }
        },
        {
          selector: 'edge',
          style: {
            'line-color': '#87867f',
            'width': 1,
            'curve-style': 'bezier'
          }
        }
      ],
      layout: {
        name: 'cose',
        idealEdgeLength: 100,
        nodeOverlap: 20,
        refresh: 20,
        fit: true,
        padding: 30,
        randomize: false,
        componentSpacing: 100,
        nodeRepulsion: 400000,
        edgeElasticity: 100,
        nestingFactor: 5,
        initialTemp: 200,
        coolingFactor: 0.95,
        minTemp: 10
      }
    });

    // Node click event
    cy.on('tap', 'node', (event) => {
      const node = event.target;
      onNodeClick?.(node.id());
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  }, [data]);

  // Highlight nodes
  useEffect(() => {
    if (!cyRef.current) return;

    const cy = cyRef.current;
    cy.nodes().removeClass('highlighted faded');

    if (highlightedNodes.length > 0) {
      cy.nodes().forEach(node => {
        if (highlightedNodes.includes(node.id())) {
          node.addClass('highlighted');
        } else {
          node.addClass('faded');
        }
      });
    }
  }, [highlightedNodes]);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '500px',
        backgroundColor: 'var(--bg-ivory)',
        border: '1px solid var(--border-cream)',
        borderRadius: 'var(--card-radius)'
      }}
    />
  );
}
