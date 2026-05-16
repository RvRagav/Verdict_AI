// Right-side Copilot — two tabs:
//   1. Chat   — grounded Q&A over this tender's state.
//   2. Studio — co-author docs (briefs, notes, letters) with full
//                tender context. Officer types a vague need; Studio
//                clarifies once if needed, drafts, and keeps revising.
//
// Both tabs use streaming Bedrock SSE. Chat is non-cached. Studio
// is also non-cached because every turn must carry the latest
// officer edit.

import { useState } from 'react';
import { MessageSquare, FileEdit } from 'lucide-react';
import CopilotChat from './CopilotChat';
import StudioTab from './StudioTab';

type CopilotTab = 'chat' | 'studio';

export default function CopilotPanel({ tenderId }: { tenderId: string }) {
  const [tab, setTab] = useState<CopilotTab>('chat');

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-line px-2 pt-2 flex gap-1">
        <button
          type="button"
          className={`copilot-tab ${tab === 'chat' ? 'is-active' : ''}`}
          onClick={() => setTab('chat')}
          title="Ask anything about this tender"
        >
          <MessageSquare size={12} /> Chat
        </button>
        <button
          type="button"
          className={`copilot-tab ${tab === 'studio' ? 'is-active' : ''}`}
          onClick={() => setTab('studio')}
          title="Co-author a brief, note or letter"
        >
          <FileEdit size={12} /> Studio
        </button>
      </div>

      <div className="flex-1 min-h-0">
        {tab === 'chat' && <CopilotChat tenderId={tenderId} />}
        {tab === 'studio' && <StudioTab tenderId={tenderId} />}
      </div>
    </div>
  );
}
