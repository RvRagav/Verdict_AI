// Tender Copilot — streaming chat with full tender context.
// Renders Markdown + a faint violet tint so officers see at a glance
// which prose came from the AI.

import { useEffect, useRef, useState } from 'react';
import { Send } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { chatApi } from '../api/endpoints';
import { getOfficer } from '../api/client';
import { onCopilotPrefill, onCopilotSend } from '../lib/copilotBridge';
import type { ChatMessage } from '../types';

export default function CopilotChat({ tenderId }: { tenderId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const sendRef = useRef<(q: string) => void>();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    chatApi.list(tenderId).then(setMessages);
  }, [tenderId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, streamText]);

  // Listen for PREFILL events — just fill the textarea, let officer edit
  useEffect(() => {
    const unsub = onCopilotPrefill((prompt) => {
      setDraft(prompt);
      // Focus the textarea so officer can immediately edit
      setTimeout(() => textareaRef.current?.focus(), 100);
    });
    return unsub;
  }, []);

  // Listen for SEND events — auto-send immediately
  useEffect(() => {
    const unsub = onCopilotSend((prompt) => {
      if (sendRef.current && !streaming) {
        sendRef.current(prompt);
      }
    });
    return unsub;
  }, [streaming]);

  async function send(overrideQuestion?: string) {
    const q = (overrideQuestion || draft).trim();
    if (!q || streaming) return;
    if (!overrideQuestion) setDraft('');
    setStreaming(true);
    setStreamText('');
    setMessages(prev => [
      ...prev,
      {
        id: `tmp-${Date.now()}`,
        tender_id: tenderId,
        role: 'user',
        content: q,
        timestamp: new Date().toISOString(),
      },
    ]);

    try {
      const url = chatApi.streamUrl(tenderId);
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Officer-ID': getOfficer(),
        },
        body: JSON.stringify({ question: q }),
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
                  tender_id: tenderId,
                  role: 'assistant',
                  content: acc,
                  timestamp: new Date().toISOString(),
                },
              ]);
              setStreamText('');
            } else if (evt.type === 'error') {
              setMessages(prev => [
                ...prev,
                {
                  id: `err-${Date.now()}`,
                  tender_id: tenderId,
                  role: 'system',
                  content: `Copilot error: ${evt.error}`,
                  timestamp: new Date().toISOString(),
                },
              ]);
              setStreamText('');
            }
          } catch {
            // ignore parse errors mid-stream
          }
        }
      }
    } finally {
      setStreaming(false);
    }
  }

  // Expose send to the bridge ref
  sendRef.current = send;

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-auto px-3 py-3 space-y-3">
        {messages.length === 0 && !streaming && (
          <div className="text-sm text-ink-soft p-3 bg-bg-sunk rounded-md">
            <div className="font-semibold text-ink mb-1">Hi, I'm your Tender Copilot.</div>
            Ask me anything about this tender. I have full access to its
            documents, criteria, bidders, verdicts, <strong>your comments</strong>,
            concurrence decisions, and the TEC report draft. Try:
            <ul className="mt-2 space-y-1 list-disc pl-4">
              <li>"Which bidder is missing the most documents?"</li>
              <li>"What did the AI say about Acme's turnover?"</li>
              <li>"What comments did officers leave on this tender?"</li>
              <li>"Regenerate the findings section considering my concerns."</li>
              <li>"What was the concurrence decision on the override?"</li>
            </ul>
          </div>
        )}

        {messages.map(m => (
          <Message key={m.id} role={m.role}>{m.content}</Message>
        ))}
        {streaming && streamText && (
          <Message role="assistant">
            {streamText}
            <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse" />
          </Message>
        )}
      </div>

      <form
        className="border-t border-line p-3 flex items-end gap-2"
        onSubmit={e => { e.preventDefault(); send(); }}
      >
        <textarea
          className="textarea text-sm"
          ref={textareaRef}
          placeholder="Ask about this tender …"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          rows={2}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          disabled={streaming}
          aria-label="Copilot question"
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!draft.trim() || streaming}
          aria-label="Send"
        >
          <Send size={14} />
        </button>
      </form>
    </div>
  );
}

function Message({ role, children }: { role: ChatMessage['role']; children: React.ReactNode }) {
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
  // Assistant — render as Markdown with the AI bubble styling.
  const text = typeof children === 'string'
    ? children
    : Array.isArray(children)
      ? children.map(c => (typeof c === 'string' ? c : '')).join('')
      : '';
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
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
        </div>
        {!text && <span className="inline-block w-2 h-4 bg-primary animate-pulse" />}
      </div>
    </div>
  );
}
