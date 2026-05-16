// Settings — workspace info, signed-in officer, AI status.
// Read-only for now; this page proves the route works and surfaces
// the sovereign-grade slug.

import { useEffect, useState } from 'react';
import { Settings as SettingsIcon, Server, User, Database } from 'lucide-react';
import { healthApi, officersApi } from '../api/endpoints';
import { getOfficer } from '../api/client';
import type { Health, Officer } from '../types';
import { Card, CardBody, CardHeader } from '../components/Card';
import Pill from '../components/Pill';

export default function Settings() {
  const [health, setHealth] = useState<Health | null>(null);
  const [officers, setOfficers] = useState<Officer[]>([]);
  const me = getOfficer();

  useEffect(() => {
    healthApi.get().then(setHealth).catch(() => {});
    officersApi.list().then(setOfficers).catch(() => {});
  }, []);

  const myOfficer = officers.find(o => o.id === me);

  return (
    <div className="hero hero-gradient mx-auto max-w-[1200px] px-6 py-10">
      <div className="hero-eyebrow flex items-center gap-2">
        <SettingsIcon size={12} /> Settings
      </div>
      <h1 className="hero-title">Your workspace, at a glance.</h1>
      <p className="hero-sub">
        Identity, AI status and storage. Everything runs locally except the Bedrock model call.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
        <Card>
          <CardHeader
            title={<span className="flex items-center gap-2"><User size={14} /> Signed in</span>}
            subtitle="The officer responsible for the next action."
          />
          <CardBody>
            {myOfficer ? (
              <>
                <div className="text-md font-semibold text-ink">{myOfficer.name}</div>
                <div className="text-sm text-ink-soft">
                  {myOfficer.department} · {myOfficer.role}
                </div>
                <div className="mono text-[11px] text-ink-faint mt-2">{myOfficer.id}</div>
              </>
            ) : (
              <div className="text-sm text-ink-soft">No officer selected. Use the picker in the topbar.</div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title={<span className="flex items-center gap-2"><Server size={14} /> AI engine</span>}
            subtitle="The reasoning + vision model behind every decision."
            actions={
              health?.bedrock?.configured
                ? <Pill tone="success">Connected</Pill>
                : <Pill tone="warning">Not configured</Pill>
            }
          />
          <CardBody>
            {health ? (
              <>
                <div className="text-sm">
                  Region: <span className="mono">{health.bedrock?.region}</span>
                </div>
                <div className="text-sm mt-1">
                  Model: <span className="mono text-[12px]">{health.bedrock?.model_id}</span>
                </div>
                <div className="text-xs text-ink-soft mt-2">
                  Build version: <span className="mono">{health.version}</span>
                </div>
              </>
            ) : (
              <div className="text-sm text-ink-soft">Loading…</div>
            )}
          </CardBody>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader
            title={<span className="flex items-center gap-2"><Database size={14} /> Storage</span>}
            subtitle="Where the dossiers, evidence and audit chain live on this machine."
          />
          <CardBody>
            <ul className="text-sm text-ink space-y-1.5">
              <li>Database: <span className="mono">verdict_ai.db</span> (SQLite, append-only triggers on audit + criterion versions)</li>
              <li>Uploaded documents: <span className="mono">uploads/</span></li>
              <li>Page rasters: <span className="mono">pages/</span></li>
              <li>TEC reports: <span className="mono">reports/</span></li>
              <li>Defence vaults: <span className="mono">vaults/</span></li>
            </ul>
            <div className="text-xs text-ink-soft mt-3 italic">
              Nothing leaves this machine except the Bedrock model call.
              Source documents are never sent to the model — only extracted text and rendered page images,
              and only when the officer requests an evaluation.
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
