// Evidence Graph — Visual provenance map for one evaluation cell.
// Shows the complete chain: criterion → bidder → source → value → branches → verdict → decision
// Rendered as a vertical flow diagram with colored nodes and connecting lines.

import { useEffect, useState } from 'react';
import api from '../api/client';

type GraphNode = {
  id: string;
  type: string;
  label: string;
  data: Record<string, any>;
};

type GraphEdge = {
  source: string;
  target: string;
  label: string;
};

type GraphData = {
  evaluation_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta: Record<string, any>;
};

const NODE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  criterion:  { bg: '#e3f2fd', border: '#1565c0', text: '#0d47a1' },
  bidder:     { bg: '#f3e5f5', border: '#6a1b9a', text: '#4a148c' },
  document:   { bg: '#fff3e0', border: '#e65100', text: '#bf360c' },
  value:      { bg: '#e8f5e9', border: '#2e7d32', text: '#1b5e20' },
  branch:     { bg: '#fce4ec', border: '#c62828', text: '#b71c1c' },
  verdict:    { bg: '#fff9c4', border: '#f9a825', text: '#f57f17' },
  dissent:    { bg: '#ffebee', border: '#d32f2f', text: '#c62828' },
  anomaly:    { bg: '#fbe9e7', border: '#d84315', text: '#bf360c' },
  decision:   { bg: '#e0f2f1', border: '#00695c', text: '#004d40' },
  comments:   { bg: '#f1f8e9', border: '#558b2f', text: '#33691e' },
};

export default function EvidenceGraph({ evaluationId }: { evaluationId: string }) {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!evaluationId) return;
    setLoading(true);
    api.get(`/evaluations/${evaluationId}/evidence-graph`)
      .then(res => { setGraph(res.data); setError(null); })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [evaluationId]);

  if (loading) return <div style={{ padding: '16px', color: 'var(--ink-soft)', fontSize: '12px' }}>Loading evidence graph...</div>;
  if (error) return <div style={{ padding: '16px', color: 'var(--danger)', fontSize: '12px' }}>Error: {error}</div>;
  if (!graph) return null;

  // Arrange nodes in a vertical flow
  const nodeOrder = ['criterion', 'bidder', 'source_doc', 'extracted_value', 'rules_branch', 'llm_branch', 'verdict', 'dissent', 'officer_decision', 'comments'];
  const orderedNodes = [...graph.nodes].sort((a, b) => {
    const ai = nodeOrder.indexOf(a.id);
    const bi = nodeOrder.indexOf(b.id);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  // Group: main flow (vertical) + side nodes (anomalies)
  const mainNodes = orderedNodes.filter(n => !n.id.startsWith('anomaly_'));
  const anomalyNodes = orderedNodes.filter(n => n.id.startsWith('anomaly_'));

  return (
    <div style={{ padding: '12px' }}>
      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--primary)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '12px' }}>
        Evidence Provenance Graph
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: anomalyNodes.length > 0 ? '1fr 180px' : '1fr', gap: '12px' }}>
        {/* Main flow */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {mainNodes.map((node, i) => (
            <div key={node.id}>
              <NodeCard node={node} />
              {i < mainNodes.length - 1 && (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '2px 0' }}>
                  <div style={{ width: '2px', height: '12px', background: 'var(--line-strong)' }} />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Anomaly sidebar */}
        {anomalyNodes.length > 0 && (
          <div>
            <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--danger)', marginBottom: '6px', textTransform: 'uppercase' }}>
              Anomaly Flags ({anomalyNodes.length})
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {anomalyNodes.map(node => (
                <NodeCard key={node.id} node={node} compact />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function NodeCard({ node, compact = false }: { node: GraphNode; compact?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const colors = NODE_COLORS[node.type] || NODE_COLORS.criterion;

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      style={{
        background: colors.bg,
        border: `1.5px solid ${colors.border}`,
        borderRadius: '4px',
        padding: compact ? '6px 8px' : '8px 12px',
        cursor: 'pointer',
        transition: 'box-shadow 0.15s',
        boxShadow: expanded ? `0 2px 8px ${colors.border}33` : 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{
          fontSize: '9px',
          fontWeight: 700,
          color: colors.text,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          flexShrink: 0,
        }}>
          {node.type.replace('_', ' ')}
        </span>
        <span style={{
          fontSize: compact ? '10px' : '11px',
          color: '#333',
          fontWeight: 500,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: compact ? 'nowrap' : 'normal',
        }}>
          {node.label}
        </span>
      </div>

      {expanded && node.data && (
        <pre style={{
          marginTop: '6px',
          fontSize: '9px',
          fontFamily: 'var(--font-mono)',
          color: colors.text,
          background: 'rgba(255,255,255,0.6)',
          padding: '6px',
          borderRadius: '2px',
          overflow: 'auto',
          maxHeight: '120px',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}>
          {JSON.stringify(node.data, null, 2)}
        </pre>
      )}
    </div>
  );
}
