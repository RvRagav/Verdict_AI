// Bidder Comparison Radar — spider chart showing 5 dimensions per bidder.
// Uses Recharts RadarChart for professional visualization.
// One glance = which bidder is strongest across Financial, Experience, Compliance, Risk, Confidence.

import { useEffect, useState } from 'react';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend, ResponsiveContainer, Tooltip } from 'recharts';
import api from '../api/client';

type BidderScore = {
  bidder_id: string;
  company_name: string;
  scores: { financial: number; experience: number; compliance: number; risk: number; confidence: number };
  overall: number;
};

const COLORS = ['#003366', '#d4a017', '#c62828', '#2e7d32', '#6a1b9a'];

export default function BidderRadar({ tenderId }: { tenderId: string }) {
  const [data, setData] = useState<BidderScore[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/tenders/${tenderId}/bidder-radar`)
      .then(res => setData(res.data.bidders))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [tenderId]);

  if (loading) return <div style={{ padding: '16px', color: 'var(--ink-soft)', fontSize: '12px' }}>Loading radar...</div>;
  if (!data.length) return <div style={{ padding: '16px', color: 'var(--ink-soft)', fontSize: '12px' }}>No bidder data available.</div>;

  // Transform for Recharts radar format
  const dimensions = ['Financial', 'Experience', 'Compliance', 'Risk', 'Confidence'];
  const chartData = dimensions.map(dim => {
    const key = dim.toLowerCase();
    const point: any = { dimension: dim };
    data.forEach(b => {
      point[b.company_name] = b.scores[key as keyof typeof b.scores];
    });
    return point;
  });

  return (
    <div className="card" style={{ padding: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--primary)' }}>Bidder Comparison Radar</div>
          <div style={{ fontSize: '11px', color: 'var(--ink-soft)' }}>5-dimension strength analysis across all bidders</div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <RadarChart data={chartData} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
          <PolarGrid stroke="var(--line)" />
          <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fill: 'var(--ink-muted)' }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 9 }} />
          {data.map((bidder, i) => (
            <Radar
              key={bidder.bidder_id}
              name={bidder.company_name.length > 20 ? bidder.company_name.slice(0, 18) + '…' : bidder.company_name}
              dataKey={bidder.company_name}
              stroke={COLORS[i % COLORS.length]}
              fill={COLORS[i % COLORS.length]}
              fillOpacity={0.15}
              strokeWidth={2}
            />
          ))}
          <Legend wrapperStyle={{ fontSize: '11px' }} />
          <Tooltip contentStyle={{ fontSize: '11px', background: 'var(--paper)', border: '1px solid var(--line)' }} />
        </RadarChart>
      </ResponsiveContainer>

      {/* Score table below */}
      <table className="govt-table" style={{ marginTop: '12px', fontSize: '11px' }}>
        <thead>
          <tr>
            <th>Bidder</th>
            <th>Financial</th>
            <th>Experience</th>
            <th>Compliance</th>
            <th>Risk</th>
            <th>Confidence</th>
            <th>Overall</th>
          </tr>
        </thead>
        <tbody>
          {data.map((b, i) => (
            <tr key={b.bidder_id}>
              <td style={{ fontWeight: 600 }}>
                <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: COLORS[i % COLORS.length], marginRight: '6px' }} />
                {b.company_name}
              </td>
              <td>{b.scores.financial}</td>
              <td>{b.scores.experience}</td>
              <td>{b.scores.compliance}</td>
              <td>{b.scores.risk}</td>
              <td>{b.scores.confidence.toFixed(0)}</td>
              <td style={{ fontWeight: 700, color: b.overall >= 60 ? 'var(--success)' : b.overall >= 40 ? 'var(--warning)' : 'var(--danger)' }}>
                {b.overall}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
