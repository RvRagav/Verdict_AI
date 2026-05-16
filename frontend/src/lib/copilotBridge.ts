// Bridge between any component and the Copilot chat panel.
// Dispatches a custom DOM event that CopilotChat listens for.
// This lets ReportView (or any other component) send a pre-filled
// prompt to the copilot without prop-drilling through the layout.

const COPILOT_PREFILL_EVENT = 'verdictai:copilot-prefill';
const COPILOT_SEND_EVENT = 'verdictai:copilot-send';

export type CopilotPromptEvent = CustomEvent<{ prompt: string }>;

/**
 * Pre-fill the Copilot chat input so the officer can edit before sending.
 * The officer sees the prompt in the textarea and can modify it.
 */
export function prefillCopilot(prompt: string): void {
  window.dispatchEvent(
    new CustomEvent(COPILOT_PREFILL_EVENT, { detail: { prompt } }),
  );
}

/**
 * Send a message to the Copilot chat immediately (auto-sends).
 * Use sparingly — prefer prefillCopilot so the officer stays in control.
 */
export function sendToCopilot(prompt: string): void {
  window.dispatchEvent(
    new CustomEvent(COPILOT_SEND_EVENT, { detail: { prompt } }),
  );
}

/**
 * Subscribe to copilot prefill events. Returns an unsubscribe function.
 */
export function onCopilotPrefill(handler: (prompt: string) => void): () => void {
  const listener = (e: Event) => {
    const detail = (e as CopilotPromptEvent).detail;
    if (detail?.prompt) handler(detail.prompt);
  };
  window.addEventListener(COPILOT_PREFILL_EVENT, listener);
  return () => window.removeEventListener(COPILOT_PREFILL_EVENT, listener);
}

/**
 * Subscribe to copilot send events. Returns an unsubscribe function.
 */
export function onCopilotSend(handler: (prompt: string) => void): () => void {
  const listener = (e: Event) => {
    const detail = (e as CopilotPromptEvent).detail;
    if (detail?.prompt) handler(detail.prompt);
  };
  window.addEventListener(COPILOT_SEND_EVENT, listener);
  return () => window.removeEventListener(COPILOT_SEND_EVENT, listener);
}
