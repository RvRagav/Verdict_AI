// Risk Heatmap — visual overlay showing risk concentration across the matrix.
// Red = high anomaly + dissent. Amber = medium. Green = clean.
// Uses a bar chart showing risk distribution + per-bidder risk breakdown.

import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import api from '../api/client';

type HeatmapCell = {
  evaluation_id: string;
  bidder_id: string;
  criterion_id: string;
  risk_score: number;
  risk_level: 'high' | 'medium' | 'low';
  factors: { anomaly: number; dissent: number; confidence_gap: number };
};

type HeatmapData = {
  cells: HeatmapCell[];
  summary: { total: number; high_risk: number; medium_risk: number; low_risk: number };
};

const RISK_COLORS = { high: '#c62828', medium: '#f9a825', low: '#2e7d32' };

export default function RiskHeatmap({ tenderId }: { tenderId: string }) {
  const [data, setData] = useState<HeatmapData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/tenders/${tenderId}/risk-heatmap`)
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [tenderId]);

  if (loading) return <div style={{ padding: '16px', color: 'var(--ink-soft)', fontSize: '12px' }}>Loading heatmap...</div>;
  if (!data) return null;

  // Group by bidder for the bar chart
  const bidderRisk: Record<string, { high: number; medium: number; low: number }> = {};
  for (const cell of data.cells) {
    if (!bidderRisk[cell.bidder_id]) bidderRisk[cell.bidder_id] = { high: 0, medium: 0, low: 0 };
    bidderRisk[cell.bidder_id][cell.risk_level]++;
  }

  // Get bidder names — use first 8 chars of ID as label
  const chartData = Object.entries(bidderRisk).map(([bid, counts]) => ({
    bidder: bid.slice(0, 8),
    high: counts.high,
    medium: counts.medium,
    low: counts.low,
  }));

  // Factor breakdown chart
  const factorData = [
    { name: 'Anomaly', value: data.cells.reduce((s, c) => s + c.factors.anomaly, 0) / Math.max(data.cells.length, 1) },
    { name: 'Dissent', value: data.cells.reduce((s, c) => s + c.factors.dissent, 0) / Math.max(data.cells.length, 1) },
    { name: 'Conf. Gap', value: data.cells.reduce((s, c) => s + c.factors.confidence_gap, 0) / Math.max(data.cells.length, 1) },
  ];

  return (
    <div className="card" style={{ padding: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--primary)' }}>Risk Heatmap</div>
          <div style={{ fontSize: '11px', color: 'var(--ink-soft)' }}>Anomaly concentration + dissent severity + confidence gaps</div>
        </div>
        <div style={{ display: 'flex', gap: '12px', fontSize: '11px' }}>
          <span><span style={{ display: 'inline-block', width: '10px', height: '10px', background: RISK_COLORS.high, borderRadius: '2px', marginRight: '4px' }} />High ({data.summary.high_risk})</span>
          <span><span style={{ display: 'inline-block', width: '10px', height: '10px', background: RISK_COLORS.medium, borderRadius: '2px', marginRight: '4px' }} />Medium ({data.summary.medium_risk})</span>
          <span><span style={{ display: 'inline-block', width: '10px', height: '10px', background: RISK_COLORS.low, borderRadius: '2px', marginRight: '4px' }} />Low ({data.summary.low_risk})</span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        {/* Risk distribution per bidder */}
        <div>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink-muted)', marginBottom: '8px' }}>Risk by Bidder</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis type="number" tick={{ fontSize: 10 }} />
              <YAxis type="category" dataKey="bidder" tick={{ fontSize: 9 }} width={60} />
              <Tooltip contentStyle={{ fontSize: '10px' }} />
              <Bar dataKey="high" stackId="a" fill={RISK_COLORS.high} name="High" />
              <Bar dataKey="medium" stackId="a" fill={RISK_COLORS.medium} name="Medium" />
              <Bar dataKey="low" stackId="a" fill={RISK_COLORS.low} name="Low" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Average risk factors */}
        <div>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink-muted)', marginBottom: '8px' }}>Average Risk Factors</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={factorData} margin={{ left: 0, right: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 9 }} />
              <Tooltip contentStyle={{ fontSize: '10px' }} />
              <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                {factorData.map((entry, i) => (
                  <Cell key={i} fill={entry.value > 0.5 ? RISK_COLORS.high : entry.value > 0.25 ? RISK_COLORS.medium : RISK_COLORS.low} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
