// New tender — single form, validates, creates, navigates into the space.

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { tendersApi } from '../api/endpoints';
import { Card, CardBody, CardHeader } from '../components/Card';
import Button from '../components/Button';
import { useToast } from '../components/Toast';

export default function NewTender() {
  const [form, setForm] = useState({
    tender_number: '', title: '', department: 'CRPF', category: 'Goods',
    estimated_cost: '', emd_amount: '',
    bid_open_date: '', bid_close_date: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const nav = useNavigate();
  const toast = useToast();

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.tender_number.trim() || !form.title.trim()) {
      toast('Tender number and title are required.', 'error');
      return;
    }
    setSubmitting(true);
    try {
      const t = await tendersApi.create({
        tender_number: form.tender_number.trim(),
        title: form.title.trim(),
        department: form.department,
        category: form.category,
        estimated_cost: form.estimated_cost ? Number(form.estimated_cost) : undefined,
        emd_amount: form.emd_amount ? Number(form.emd_amount) : undefined,
        bid_open_date: form.bid_open_date || undefined,
        bid_close_date: form.bid_close_date || undefined,
      });
      // Move to DOCUMENTS_PENDING so user can start uploading
      try {
        await tendersApi.transition(t.id, 'DOCUMENTS_PENDING');
      } catch {/* ignore — UI will just show DRAFT */}
      toast('Tender created.', 'success');
      nav(`/tenders/${t.id}/documents`);
    } catch (err) {
      toast((err as Error).message, 'error');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-[820px] px-6 py-8">
      <button onClick={() => nav('/')} className="btn btn-ghost btn-sm mb-4">
        <ArrowLeft size={14} /> Back to dashboard
      </button>
      <Card>
        <CardHeader title="New tender" subtitle="Set up the workspace for a new procurement." />
        <CardBody>
          <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="label">Tender number *</label>
              <input className="input" required value={form.tender_number} onChange={set('tender_number')} placeholder="e.g. CRPF/2026/15-A" />
            </div>
            <div className="md:col-span-2">
              <label className="label">Title *</label>
              <input className="input" required value={form.title} onChange={set('title')} placeholder="e.g. Supply of Patrol Vehicles" />
            </div>
            <div>
              <label className="label">Department</label>
              <select className="select" value={form.department} onChange={set('department')}>
                <option>CRPF</option>
                <option>BSF</option>
                <option>CISF</option>
                <option>SSB</option>
                <option>ITBP</option>
                <option>NSG</option>
                <option>Other</option>
              </select>
            </div>
            <div>
              <label className="label">Category</label>
              <select className="select" value={form.category} onChange={set('category')}>
                <option>Goods</option>
                <option>Services</option>
                <option>Works</option>
                <option>Consultancy</option>
              </select>
            </div>
            <div>
              <label className="label">Estimated cost (₹)</label>
              <input className="input" type="number" min={0} value={form.estimated_cost} onChange={set('estimated_cost')} />
            </div>
            <div>
              <label className="label">EMD amount (₹)</label>
              <input className="input" type="number" min={0} value={form.emd_amount} onChange={set('emd_amount')} />
            </div>
            <div>
              <label className="label">Bid open date</label>
              <input className="input" type="date" value={form.bid_open_date} onChange={set('bid_open_date')} />
            </div>
            <div>
              <label className="label">Bid close date</label>
              <input className="input" type="date" value={form.bid_close_date} onChange={set('bid_close_date')} />
            </div>
            <div className="md:col-span-2 flex justify-end pt-2">
              <Button
                type="submit"
                variant="primary"
                icon={<ArrowRight size={14} />}
                disabled={submitting}
              >
                {submitting ? 'Creating…' : 'Create & continue'}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}
