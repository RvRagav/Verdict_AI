// Document Studio — second Copilot tab.
//
// Officer flow:
//   1. Pick or create a doc ("brief for my CO", "note explaining
//      corrigendum impact").
//   2. Type what they need. Studio asks one clarifying question if
//      vague, then drafts a Markdown document grounded in the
//      tender's data.
//   3. Officer keeps chatting ("shorten section 2", "add the
//      smell-test signals"). Studio returns the FULL revised doc
//      in a <document> block each turn — we extract and live-preview.
//   4. Click "Finalise" — doc is hash-stamped, marked finalised,
//      lands in the File Vault as officer_authored.

import { useEffect, useRef, useState } from 'react';
import { Send, FileText, Plus, Download, Lock } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { studioApi } from '../api/endpoints';
import { getOfficer } from '../api/client';
import { useToast } from './Toast';
import Button from './Button';
import type { StudioDoc, StudioMessage } from '../types';

export default function StudioTab({ tenderId }: { tenderId: string }) {
  const [docs, setDocs] = useState<StudioDoc[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState('');

  const refresh = () => studioApi.list(tenderId).then(setDocs);

  useEffect(() => { refresh(); }, [tenderId]);

  // Auto-select most recent draft when docs load
  useEffect(() => {
    if (docs.length > 0 && !activeId) {
      const draft = docs.find(d => d.state === 'draft') || docs[0];
      setActiveId(draft.id);
    }
  }, [docs, activeId]);

  async function createDoc() {
    if (!newTitle.trim()) return;
    try {
      const d = await studioApi.create(tenderId, { title: newTitle.trim() });
      setNewTitle('');
      setCreating(false);
      await refresh();
      setActiveId(d.id);
    } catch {/* toast handled below */}
  }

  const active = docs.find(d => d.id === activeId);

  return (
    <div className="flex flex-col h-full">
      {/* Top bar — picker + new */}
      <div className="border-b border-line p-2 flex items-center gap-2">
        <select
          className="select text-xs flex-1"
          value={activeId || ''}
          onChange={e => setActiveId(e.target.value || null)}
          aria-label="Active document"
        >
          <option value="">— pick a document —</option>
          {docs.map(d => (
            <option key={d.id} value={d.id}>
              {d.title} {d.state === 'finalised' ? '· locked' : ''}
            </option>
          ))}
        </select>
        <Button
          variant="primary"
          size="sm"
          icon={<Plus size={11} />}
          onClick={() => setCreating(c => !c)}
          title="New document"
        >
          New
        </Button>
      </div>

      {creating && (
        <div className="border-b border-line p-2 bg-bg-sunk flex items-center gap-2">
          <input
            className="input text-xs flex-1"
            placeholder="e.g. Brief for CO on this tender"
            value={newTitle}
            onChange={e => setNewTitle(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') createDoc(); }}
            autoFocus
          />
          <Button
            variant="success"
            size="sm"
            disabled={!newTitle.trim()}
            onClick={createDoc}
          >
            Create
          </Button>
        </div>
      )}

      {!active && (
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-sm text-ink-soft text-center max-w-[28ch]">
            <FileText size={28} className="mx-auto mb-2 text-ink-faint" />
            Studio drafts briefs, notes and letters with full tender
            context. Click <b>New</b> to start one.
          </div>
        </div>
      )}

      {active && <StudioDocView key={active.id} doc={active} onChanged={refresh} />}
    </div>
  );
}

// ─── One-doc view ────────────────────────────────────────────────────

function StudioDocView({ doc, onChanged }: { doc: StudioDoc; onChanged: () => void }) {
  const [messages, setMessages] = useState<StudioMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState('');
  const [previewBody, setPreviewBody] = useState(doc.rendered_body || '');
  const [showPreview, setShowPreview] = useState(Boolean(doc.rendered_body));
  const scrollRef = useRef<HTMLDivElement>(null);
  const toast = useToast();

  const finalised = doc.state === 'finalised';

  useEffect(() => {
    studioApi.messages(doc.id).then(setMessages);
    setPreviewBody(doc.rendered_body || '');
  }, [doc.id, doc.rendered_body]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight, behavior: 'smooth',
    });
  }, [messages, streamText]);

  async function send() {
    const q = draft.trim();
    if (!q || streaming || finalised) return;
    setDraft('');
    setStreaming(true);
    setStreamText('');
    setMessages(prev => [
      ...prev,
      {
        id: `tmp-${Date.now()}`,
        document_id: doc.id,
        role: 'user',
        content: q,
        timestamp: new Date().toISOString(),
      },
    ]);

    try {
      const res = await fetch(studioApi.streamUrl(doc.id), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Officer-ID': getOfficer(),
        },
        body: JSON.stringify({ message: q }),
      });
      if (!res.body) throw new Error('No response body');
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let acc = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          const m = line.match(/^data:\s*(.*)$/);
          if (!m) continue;
          try {
            const evt = JSON.parse(m[1]);
            if (evt.type === 'delta') {
              acc += evt.text;
              setStreamText(acc);
            } else if (evt.type === 'done') {
              acc = evt.text || acc;
              setMessages(prev => [
                ...prev,
                {
                  id: evt.assistant_message_id || `assistant-${Date.now()}`,
                  document_id: doc.id,
                  role: 'assistant',
                  content: acc,
                  rendered_body: evt.rendered_body || null,
                  timestamp: new Date().toISOString(),
                },
              ]);
              if (evt.rendered_body) {
                setPreviewBody(evt.rendered_body);
              }
              setStreamText('');
            } else if (evt.type === 'error') {
              setMessages(prev => [
                ...prev,
                {
                  id: `err-${Date.now()}`,
                  document_id: doc.id,
                  role: 'system',
                  content: `Studio error: ${evt.error}`,
                  timestamp: new Date().toISOString(),
                },
              ]);
              setStreamText('');
            }
          } catch {/* ignore */}
        }
      }
    } catch (e) {
      toast(`Stream failed: ${(e as Error).message}`, 'error');
    } finally {
      setStreaming(false);
    }
  }

  async function finalise() {
    if (!previewBody.trim()) {
      toast('Add some content before finalising.', 'error');
      return;
    }
    try {
      await studioApi.finalise(doc.id);
      toast('Document finalised.', 'success');
      onChanged();
    } catch (e) {
      toast(`Finalise failed: ${(e as Error).message}`, 'error');
    }
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Toggle: chat | preview */}
      <div className="border-b border-line px-2 py-1 flex items-center gap-1 text-[11px]">
        <button
          type="button"
          className={`copilot-tab ${!showPreview ? 'is-active' : ''}`}
          onClick={() => setShowPreview(false)}
        >
          Chat
        </button>
        <button
          type="button"
          className={`copilot-tab ${showPreview ? 'is-active' : ''}`}
          onClick={() => setShowPreview(true)}
        >
          Preview
        </button>
        <div className="ml-auto flex items-center gap-1">
          {finalised ? (
            <>
              <span className="text-[10px] text-ink-soft inline-flex items-center gap-1">
                <Lock size={10} /> finalised
              </span>
              <a
                href={studioApi.downloadUrl(doc.id)}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-ghost btn-sm inline-flex items-center gap-1"
                title="Download Markdown"
              >
                <Download size={11} /> Download
              </a>
            </>
          ) : (
            <Button
              variant="success"
              size="sm"
              icon={<Lock size={11} />}
              onClick={finalise}
              disabled={!previewBody.trim()}
              title="Lock the document and write to vault"
            >
              Finalise
            </Button>
          )}
        </div>
      </div>

      {showPreview ? (
        <div className="flex-1 overflow-auto px-3 py-3">
          {previewBody ? (
            <div className="ai-md text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{previewBody}</ReactMarkdown>
            </div>
          ) : (
            <div className="text-sm text-ink-soft p-3 bg-bg-sunk rounded-md">
              No draft yet. Switch to <b>Chat</b> and tell Studio what you need.
            </div>
          )}
        </div>
      ) : (
        <div ref={scrollRef} className="flex-1 overflow-auto px-3 py-3 space-y-3">
          {messages.length === 0 && !streaming && (
            <div className="text-sm text-ink-soft p-3 bg-bg-sunk rounded-md">
              <div className="font-semibold text-ink mb-1">Studio is ready.</div>
              Tell me what document you need. Try:
              <ul className="mt-2 space-y-1 list-disc pl-4">
                <li>"Brief for CO with smell-test signals."</li>
                <li>"Note to vendor explaining the corrigendum."</li>
                <li>"One-page summary of why we excluded Bravo."</li>
              </ul>
            </div>
          )}
          {messages.map(m => <StudioMsg key={m.id} role={m.role}>{m.content}</StudioMsg>)}
          {streaming && streamText && (
            <StudioMsg role="assistant">
              {streamText}
              <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse" />
            </StudioMsg>
          )}
        </div>
      )}

      <form
        className="border-t border-line p-2 flex items-end gap-2"
        onSubmit={e => { e.preventDefault(); send(); }}
      >
        <textarea
          className="textarea text-sm"
          placeholder={finalised ? 'Document is finalised.' : 'Tell Studio what to write or change …'}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          rows={2}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          disabled={streaming || finalised}
          aria-label="Studio message"
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!draft.trim() || streaming || finalised}
          aria-label="Send"
        >
          <Send size={14} />
        </button>
      </form>
    </div>
  );
}

function StudioMsg({ role, children }: { role: StudioMessage['role']; children: React.ReactNode }) {
  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] px-3 py-2 rounded-lg bg-primary text-ink-on text-sm whitespace-pre-wrap">
          {children}
        </div>
      </div>
    );
  }
  if (role === 'system') {
    return (
      <div className="text-xs text-danger bg-danger-soft border border-danger rounded-md p-2">
        {children}
      </div>
    );
  }
  // Render Markdown — but strip the <document>...</document> block
  // from chat preview, since the doc itself is shown in the Preview tab.
  const raw = typeof children === 'string' ? children : '';
  const stripped = raw.replace(/<document>[\s\S]*?<\/document>/i, '_(document updated — see Preview tab)_').trim();
  return (
    <div className="flex justify-start">
      <div
        className="max-w-[92%] px-3 py-2.5 rounded-lg text-sm ai-bubble"
        style={{
          background: 'linear-gradient(180deg, #f5f1fb 0%, #ecf1fa 100%)',
          border: '1px solid #cdd5e9',
          color: 'var(--ink)',
        }}
      >
        <div className="ai-md">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{stripped || (typeof children === 'object' ? '' : raw)}</ReactMarkdown>
        </div>
        {typeof children !== 'string' && children}
      </div>
    </div>
  );
}
