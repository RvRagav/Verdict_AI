// Help & Documentation — Two tabs (User Guide + About System)
// Full-width layout with left sidebar TOC navigation.
// Content is deep, precise, short sentences. What/why/how for everything.

import { useState, useRef } from 'react';
import { BookOpen, Cpu } from 'lucide-react';

type Tab = 'guide' | 'system';

const GUIDE_SECTIONS = [
  { id: 'overview', label: 'System Overview' },
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'new-dossier', label: 'Creating a Dossier' },
  { id: 'documents', label: 'Document Upload' },
  { id: 'criteria', label: 'Criteria Extraction' },
  { id: 'evaluation', label: 'Evaluation Matrix' },
  { id: 'drawer', label: 'Cell Detail Drawer' },
  { id: 'anomalies', label: 'Anomaly Detection' },
  { id: 'report', label: 'TEC Report' },
  { id: 'studio', label: 'Document Studio' },
  { id: 'verifiers', label: 'External Verifiers' },
  { id: 'vault', label: 'Defence Vault' },
  { id: 'audit', label: 'Audit Chain' },
  { id: 'copilot', label: 'AI Copilot' },
  { id: 'concurrence', label: 'Concurrence Flow' },
];

const SYSTEM_SECTIONS = [
  { id: 'problem', label: 'Problem Statement' },
  { id: 'design', label: 'Design Philosophy' },
  { id: 'architecture', label: 'Module Architecture' },
  { id: 'pipeline', label: 'Data Pipeline' },
  { id: 'dual-branch', label: 'Dual-Branch Extraction' },
  { id: 'mosaic', label: 'Confidence Mosaic' },
  { id: 'dissent', label: 'Devil\'s Advocate' },
  { id: 'statistical', label: 'Statistical Fraud Detection' },
  { id: 'entity', label: 'Entity Resolution' },
  { id: 'security-scan', label: 'Document Security' },
  { id: 'hash-chain', label: 'Hash Chain Audit' },
  { id: 'verifier-arch', label: 'Verifier Architecture' },
  { id: 'stack', label: 'Technology Stack' },
  { id: 'sovereignty', label: 'Data Sovereignty' },
  { id: 'limitations', label: 'Honest Limitations' },
  { id: 'metrics', label: 'System Metrics' },
];

export default function Help() {
  const [tab, setTab] = useState<Tab>('guide');
  const [activeSection, setActiveSection] = useState('');
  const contentRef = useRef<HTMLDivElement>(null);

  const sections = tab === 'guide' ? GUIDE_SECTIONS : SYSTEM_SECTIONS;

  function scrollTo(id: string) {
    setActiveSection(id);
    const el = document.getElementById(id);
    if (el && contentRef.current) {
      const top = el.offsetTop - 12;
      contentRef.current.scrollTo({ top, behavior: 'smooth' });
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '0', height: 'calc(100vh - 300px)', minHeight: '500px' }}>
      {/* Left TOC Sidebar */}
      <div style={{ borderRight: '1px solid var(--line)', padding: '12px 0', overflowY: 'auto', background: 'var(--paper)' }}>
        {/* Tab switcher */}
        <div style={{ padding: '0 12px 12px', borderBottom: '1px solid var(--line)', marginBottom: '8px' }}>
          <button onClick={() => setTab('guide')} style={{ display: 'flex', alignItems: 'center', gap: '4px', width: '100%', padding: '6px 8px', fontSize: '12px', fontWeight: tab === 'guide' ? 700 : 500, color: tab === 'guide' ? 'var(--primary)' : 'var(--ink-muted)', background: tab === 'guide' ? 'var(--primary-soft)' : 'transparent', border: 'none', borderRadius: '3px', cursor: 'pointer', marginBottom: '4px', textAlign: 'left' }}>
            <BookOpen size={12} /> User Guide
          </button>
          <button onClick={() => setTab('system')} style={{ display: 'flex', alignItems: 'center', gap: '4px', width: '100%', padding: '6px 8px', fontSize: '12px', fontWeight: tab === 'system' ? 700 : 500, color: tab === 'system' ? 'var(--primary)' : 'var(--ink-muted)', background: tab === 'system' ? 'var(--primary-soft)' : 'transparent', border: 'none', borderRadius: '3px', cursor: 'pointer', textAlign: 'left' }}>
            <Cpu size={12} /> About System
          </button>
        </div>
        {/* Section links */}
        <div style={{ padding: '0 8px' }}>
          {sections.map(s => (
            <button key={s.id} onClick={() => scrollTo(s.id)} style={{ display: 'block', width: '100%', textAlign: 'left', padding: '5px 8px', fontSize: '11px', color: activeSection === s.id ? 'var(--primary)' : 'var(--ink-muted)', fontWeight: activeSection === s.id ? 600 : 400, background: 'transparent', border: 'none', borderLeft: activeSection === s.id ? '2px solid var(--primary)' : '2px solid transparent', cursor: 'pointer', marginBottom: '1px' }}>
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Right Content */}
      <div ref={contentRef} style={{ overflowY: 'auto', padding: '20px 28px', scrollbarWidth: 'thin' }}>
        {tab === 'guide' ? <UserGuide /> : <AboutSystem />}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════
// USER GUIDE
// ═══════════════════════════════════════════════════════════════════

function UserGuide() {
  return (
    <div style={{ fontSize: '13px', lineHeight: 1.7, color: 'var(--ink)' }}>
      <S id="overview" title="System Overview">
        <p><b>VerdictAI</b> is a tender evaluation workspace. It reads NITs, extracts criteria, evaluates bidders, and produces a co-authored TEC report — all with a hash-chained audit trail.</p>
        <p><b>What it is:</b> Decision-support. The AI suggests; the officer decides.</p>
        <p><b>What it is NOT:</b> An auto-evaluator. It never silently disqualifies. It never fabricates evidence.</p>
        <Info>Every output carries a confidence score + source reference. Click any claim → see the PDF page it came from.</Info>
      </S>

      <S id="dashboard" title="Dashboard">
        <p><b>What you see:</b> 6 stat cards (total dossiers, active evaluations, pending reviews, bidders, anomalies, AI status) + tender grid + activity feed + system health.</p>
        <p><b>What to do:</b> Click any tender card → opens the dossier. Click "New Dossier" → create a fresh evaluation.</p>
        <p><b>Activity feed:</b> Real-time audit events from all dossiers. Shows who did what, when.</p>
      </S>

      <S id="new-dossier" title="Creating a Dossier">
        <p><b>Fields:</b> Tender Number, Title, Department, Category, Estimated Cost (₹), EMD Amount, Bid Open/Close dates.</p>
        <p><b>What happens:</b> A dossier is created in DRAFT state. You're taken to the workspace with 8 sections in the sidebar.</p>
        <p><b>Naming:</b> Use the official tender number (e.g., U.II-1410/2022-23-Proc-VII). This appears on the TEC report.</p>
      </S>

      <S id="documents" title="Document Upload & Processing">
        <p><b>Step 1:</b> Upload the NIT (Notice Inviting Tender). Mark it as type "NIT".</p>
        <p><b>Step 2:</b> Upload each bidder's submission pack. Mark each as "bidder_submission" or "certificate".</p>
        <p><b>What the system does on upload:</b></p>
        <ol>
          <li>Detects format (PDF typed/scanned, DOCX, JPG, PNG, TIFF)</li>
          <li>Runs security scan (prompt injection, hidden text, metadata forensics, PDF structure)</li>
          <li>Extracts text: Bedrock Vision for scans/photos, native extraction for typed PDFs</li>
          <li>Generates per-word bounding boxes (for source-click later)</li>
          <li>Computes SHA-256 hash (tamper detection)</li>
          <li>Records criterion_version_at_upload (Calcutta HC defensibility)</li>
        </ol>
        <Warn>If a document fails security scan (e.g., prompt injection detected), it's flagged but still processed. The officer sees the warning.</Warn>
      </S>

      <S id="criteria" title="Criteria Extraction">
        <p><b>Trigger:</b> Click "Extract Criteria" on the Criteria page.</p>
        <p><b>What the AI produces per criterion:</b></p>
        <table className="govt-table"><thead><tr><th>Field</th><th>Example</th></tr></thead><tbody>
          <tr><td>Text</td><td>"Annual turnover ≥ ₹150 Cr in each of last 3 FYs"</td></tr>
          <tr><td>Type</td><td>numeric_threshold / categorical_presence / temporal_recency / qualitative / composite</td></tr>
          <tr><td>Mandatory</td><td>Yes / No</td></tr>
          <tr><td>Threshold</td><td>{`{rupees: 1500000000, period: "each_of_3_years", n: 3}`}</td></tr>
          <tr><td>Measurement period</td><td>single / each_of_n_years / average / cumulative / any</td></tr>
          <tr><td>Source clause</td><td>Clause 4.1(a), page 2</td></tr>
          <tr><td>GFR rule</td><td>Rule 173 (if referenced)</td></tr>
        </tbody></table>
        <p><b>Officer actions:</b> Edit text, change type, approve, reject. Every edit creates a new version (append-only).</p>
      </S>

      <S id="evaluation" title="Evaluation Matrix">
        <p><b>What it shows:</b> Grid of (bidders × criteria). Each cell = one AI-suggested verdict.</p>
        <p><b>Cell colors:</b></p>
        <ul>
          <li><span style={{color:'var(--success)',fontWeight:700}}>Green</span> — "AI: satisfies" (evidence found, threshold met)</li>
          <li><span style={{color:'var(--danger)',fontWeight:700}}>Red</span> — "AI: does not satisfy" (evidence found, below threshold)</li>
          <li><span style={{color:'#856404',fontWeight:700}}>Amber</span> — "AI: unclear" (evidence missing or ambiguous)</li>
        </ul>
        <p><b>Stats bar:</b> Total cells, high-confidence count, officer-review count, mandatory-review count.</p>
        <p><b>Click any cell</b> → opens the Evaluation Drawer (see next section).</p>
      </S>

      <S id="drawer" title="Cell Detail Drawer">
        <p>The drawer is the core decision-making interface. It shows (top to bottom):</p>
        <ol>
          <li><b>Confidence Veil headline:</b> "I'm 91% confident this satisfies Clause 4.1(a)." Never says "PASS".</li>
          <li><b>Extracted evidence:</b> The actual figures found (e.g., "FY 2022-23: ₹14.50 Cr, FY 2023-24: ₹16.20 Cr")</li>
          <li><b>Source pill:</b> Click → PDF opens at exact page with highlighted region.</li>
          <li><b>Confidence Mosaic:</b> 5 bars (OCR, Extraction, Entity, Rules, LLM). Harmonic mean composite.</li>
          <li><b>Devil's Advocate:</b> A second AI argues AGAINST the verdict. Shows severity (low/medium/high).</li>
          <li><b>Anomaly flags:</b> Any smell-test signals on this cell.</li>
          <li><b>Officer notes:</b> Append-only comment thread. Your space to think out loud.</li>
          <li><b>Decision buttons:</b> Confirm verdict / Override (with new verdict + reason).</li>
        </ol>
        <Info>Override opens a concurrence request to a second officer if the criterion is mandatory.</Info>
      </S>

      <S id="anomalies" title="Anomaly Detection">
        <p><b>18 techniques</b> run automatically across all bidders:</p>
        <table className="govt-table"><thead><tr><th>Category</th><th>Techniques</th><th>Catches</th></tr></thead><tbody>
          <tr><td>Rule-based (7)</td><td>Address collision, PAN format, GSTIN-PAN mismatch, round numbers, date proximity, duplicate docs, parent-substitution</td><td>Basic fraud patterns</td></tr>
          <tr><td>Cartel (3)</td><td>Sequential DD numbers, common signatory, cover-letter verbatim overlap</td><td>CCI 2025 bid-rigging signals</td></tr>
          <tr><td>Statistical (3)</td><td>Benford's Law χ², Z-score pooling, bid-spread CV</td><td>Fabricated figures, price-fixing, cover bidding</td></tr>
          <tr><td>Forensic (2)</td><td>PDF metadata clustering, entity resolution (Jaccard)</td><td>Same-machine docs, shell companies</td></tr>
          <tr><td>Security (2)</td><td>Prompt injection, hidden text layers</td><td>Adversarial manipulation, forged scans</td></tr>
          <tr><td>AI-driven (1)</td><td>LLM novel-anomaly detection</td><td>Patterns rules miss</td></tr>
        </tbody></table>
      </S>

      <S id="report" title="TEC Report Co-Authoring">
        <p><b>Not auto-generated.</b> Co-authored. Each section has an <code>authored_by</code> chip:</p>
        <ul>
          <li><b>AI draft</b> — initial text from the AI</li>
          <li><b>Co-authored</b> — officer edited the AI's draft</li>
          <li><b>Officer-authored</b> — officer wrote from scratch</li>
        </ul>
        <p><b>Actions per section:</b> Edit (inline textarea) · Regenerate (ask AI for fresh draft) · History (see all revisions)</p>
        <p><b>Finalise:</b> Renders to PDF with sha256 hash. Every paragraph's authorship is stamped on the PDF itself.</p>
      </S>

      <S id="studio" title="Document Studio">
        <p><b>Where:</b> Copilot panel → Studio tab.</p>
        <p><b>What:</b> Officer types a vague need → AI drafts a document with full tender context → officer chats to refine → finalise to PDF.</p>
        <p><b>Examples:</b> "Brief for my CO on smell-test signals" · "Note explaining corrigendum impact" · "Summary of why we excluded Bidder X"</p>
        <p><b>Rules:</b> AI never invents figures. Missing facts → "[to be filled by officer]". Every turn returns the FULL revised document.</p>
      </S>

      <S id="verifiers" title="External Verifiers">
        <p><b>7 checks per bidder:</b> GST (active on bid-date), PAN (entity-code rule), UDIN (CA cert authenticity), FRN (firm registration), MCA (CIN status), Udyam (MSME), Debarment (CVC+GeM blacklist).</p>
        <p><b>Driver-stub pattern:</b> Each verifier has a live implementation + a stub. Stubs return deterministic results based on format/logic. Live mode = one env flag flip.</p>
        <p><b>Provenance badge:</b> Every result shows <code>stub</code> / <code>live</code> / <code>local-registry</code>. No pretending.</p>
      </S>

      <S id="vault" title="Defence Vault">
        <p><b>One click.</b> Generates a sealed ZIP containing:</p>
        <ul>
          <li>All cited PDF pages with bounding boxes</li>
          <li>Complete audit chain (JSON)</li>
          <li>Every evaluation decision snapshot</li>
          <li>Pipeline signature + prompt hashes</li>
          <li>SHA-256 manifest per file</li>
          <li><code>08_reproduce.py</code> — run on any machine to verify integrity</li>
        </ul>
        <p><b>Use case:</b> Hand to CVC/CAG 3 years later. They run one script. Every hash matches. Decision is reconstructed.</p>
      </S>

      <S id="audit" title="Audit Chain">
        <p><b>Every action</b> = one row in <code>audit_events</code>. Each row's hash = SHA-256(prev_hash + event_type + data + actor + timestamp).</p>
        <p><b>Tamper-proof:</b> DB triggers block UPDATE and DELETE at the SQLite engine level.</p>
        <p><b>Verify:</b> Click "Verify chain" → walks every event, recomputes hashes, confirms linkage.</p>
        <p><b>30+ event types:</b> tender_created, document_received, criteria_extracted, evaluation_computed, officer_comment_added, tec_report_finalised, vault_generated, etc.</p>
      </S>

      <S id="copilot" title="AI Copilot">
        <p><b>Where:</b> Right panel on every dossier page. Two tabs: Chat + Studio.</p>
        <p><b>Chat:</b> Ask anything about this tender. Grounded in the dossier's data (criteria, bidders, evaluations, anomalies). Streams via SSE.</p>
        <p><b>What it knows:</b> Tender state, all criteria, all bidders with verdict counts, open anomalies, recent decisions.</p>
        <p><b>What it won't do:</b> Invent facts. Tell you what to decide. Cite documents it hasn't read.</p>
      </S>

      <S id="concurrence" title="Concurrence Flow">
        <p><b>When:</b> Officer overrides a mandatory-review cell → concurrence request auto-opens.</p>
        <p><b>Target:</b> Routes to a "reviewer" role officer (different from the deciding officer).</p>
        <p><b>Inbox:</b> Review Queue page shows all pending concurrence requests.</p>
        <p><b>Actions:</b> Concur (approve the override) or Reject (send back for re-evaluation).</p>
        <p><b>Audit:</b> Both the request and the decision are hash-chained.</p>
      </S>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════
// ABOUT THE SYSTEM — Technical Deep-Dive
// ═══════════════════════════════════════════════════════════════════

function AboutSystem() {
  return (
    <div style={{ fontSize: '13px', lineHeight: 1.7, color: 'var(--ink)' }}>
      <S id="problem" title="Problem Statement">
        <div style={{ borderLeft: '3px solid var(--accent)', paddingLeft: '12px', fontSize: '14px', fontWeight: 600, margin: '8px 0 16px' }}>
          Reduce tender evaluation from 3-7 days to under 30 minutes. Produce a decision more defensible, auditable, and consistent than manual — without ever making the decision itself.
        </div>
        <p><b>Context:</b> CRPF evaluates 200+ tenders/year. Each involves 8-20 eligibility criteria × 3-15 bidders × 5-20 documents per bidder. Manual process: 4 officers × 3-7 days per tender.</p>
        <p><b>Constraint:</b> The system is decision-SUPPORT. GFR 2017 Rule 173 requires a human TEC member to sign. AI cannot sign.</p>
      </S>

      <S id="design" title="Design Philosophy">
        <p><b>We worked backwards from four questions:</b></p>
        <table className="govt-table"><thead><tr><th>Question</th><th>Answer</th><th>Feature</th></tr></thead><tbody>
          <tr><td>What does the officer defend 3 years later?</td><td>A sealed evidence package</td><td>Defence Vault + hash-chain</td></tr>
          <tr><td>What does the officer need RIGHT NOW?</td><td>Confidence + source</td><td>Confidence Veil + source-click</td></tr>
          <tr><td>What must the officer NOT miss?</td><td>Counter-arguments + anomalies</td><td>Devil's Advocate + 18 anomaly rules</td></tr>
          <tr><td>What must the AI NEVER do?</td><td>Decide. Disqualify. Fabricate.</td><td>Routing rules + REVIEW-not-FAIL</td></tr>
        </tbody></table>
      </S>

      <S id="architecture" title="Module Architecture">
        {/* Colorful diagram */}
        <div style={{ background: '#f8f9fa', padding: '16px', borderRadius: '4px', border: '1px solid var(--line)', marginBottom: '16px' }}>
          <div style={{ background: 'var(--primary)', color: 'white', padding: '8px 12px', borderRadius: '3px', textAlign: 'center', marginBottom: '10px', fontSize: '11px', fontWeight: 700 }}>
            M6: SECURITY & AUDIT — SHA-256 hash-chain · DB triggers · Defence Vault · Reproduce script
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '8px' }}>
            <ModuleBox color="#1565c0" bg="#e3f2fd" title="M1: Data Extraction" items={['Bedrock Vision OCR', 'Tesseract fallback', 'Per-word bounding boxes', 'Format: PDF/DOCX/JPG/PNG']} />
            <ModuleBox color="#2e7d32" bg="#e8f5e9" title="M3: Intelligence" items={['Dual-branch extraction', 'Harmonic-mean Mosaic', 'Devil\'s Advocate dissent', '18 anomaly techniques']} />
            <ModuleBox color="#e65100" bg="#fff3e0" title="M4: Human-in-the-Loop" items={['Co-authored TEC report', 'Document Studio', 'Per-cell officer notes', 'Override + concurrence']} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <ModuleBox color="#c62828" bg="#fce4ec" title="M2: Data Correctness" items={['7 external verifiers', 'Driver-stub pattern', 'Source URL + snapshot + sha256', 'Bid-date anchored checks']} />
            <ModuleBox color="#6a1b9a" bg="#f3e5f5" title="M5: Lifecycle" items={['15-state machine', 'Corrigendum chain', 'Criterion version history', 'File Vault + EMD tracking']} />
          </div>
        </div>
        <p><b>102 API endpoints.</b> 18 anomaly flag types. 30+ audit event types. 7 verifier drivers. 5 pipeline layers.</p>
      </S>

      <S id="pipeline" title="Data Pipeline (5 Layers)">
        <table className="govt-table"><thead><tr><th>Layer</th><th>Input</th><th>Output</th><th>Engine</th></tr></thead><tbody>
          <tr><td>L1: Document Processing</td><td>PDF/JPG file</td><td>Pages + word_objects + sha256</td><td>Bedrock Vision + Tesseract</td></tr>
          <tr><td>L2: Criterion Extraction</td><td>NIT text</td><td>Structured criteria with thresholds</td><td>Claude Sonnet 4.5 (structured JSON)</td></tr>
          <tr><td>L3: Evidence Extraction</td><td>Bidder docs + criterion</td><td>Extracted values + source refs</td><td>Dual-branch (regex + LLM)</td></tr>
          <tr><td>L4: Verdict + Dissent</td><td>Evidence + threshold</td><td>Verdict + confidence + dissent</td><td>Rule engine + Claude dissent</td></tr>
          <tr><td>L5: Anomaly Detection</td><td>All bidders' data</td><td>Anomaly flags (18 types)</td><td>Rules + statistics + LLM</td></tr>
        </tbody></table>
        <p><b>Every layer is cached</b> by prompt-hash. Re-running the same evaluation hits cache → identical output → reproducible.</p>
      </S>

      <S id="dual-branch" title="Dual-Branch Evidence Extraction">
        <p><b>Why:</b> A single extractor has a single point of failure. If the regex misses a table format, or the LLM hallucinates a number, the officer gets a wrong verdict with high confidence. Two independent branches cross-validate.</p>
        <p><b>How it works in practice:</b></p>
        <div style={{ background: '#f8f9fa', border: '1px solid var(--line)', borderRadius: '3px', padding: '12px', margin: '8px 0' }}>
          <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Example: Criterion "Annual turnover ≥ ₹150 Cr in each of last 3 FYs"</p>
          <p style={{ margin: '0 0 4px' }}><b>Rules branch:</b> Scans for patterns like "Rs. 1,85,00,00,000" or "₹185 Crore" or "Rupees One Hundred Eighty Five Crore". Finds: FY 2019-20: ₹185 Cr, FY 2020-21: ₹192 Cr, FY 2021-22: ₹210 Cr.</p>
          <p style={{ margin: '0 0 4px' }}><b>LLM branch:</b> Claude reads the CA certificate table, understands "Annual Turnover from Defence Vehicle Sales" column, extracts the same 3 figures.</p>
          <p style={{ margin: '0 0 4px' }}><b>Reconciliation:</b> Both branches found 3 figures. Values match. Agreement score = 1.0. Confidence = high.</p>
          <p style={{ margin: '0', color: 'var(--success)', fontWeight: 600 }}>→ Result: "AI: satisfies" with 94% confidence. All 3 years exceed ₹150 Cr threshold.</p>
        </div>
        <div style={{ background: '#fff3e0', border: '1px solid var(--warning)', borderRadius: '3px', padding: '12px', margin: '8px 0' }}>
          <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Example: Disagreement scenario</p>
          <p style={{ margin: '0 0 4px' }}><b>Rules branch:</b> Finds "₹98 Cr" in one place.</p>
          <p style={{ margin: '0 0 4px' }}><b>LLM branch:</b> Finds "₹98 Cr" for standalone + "₹125 Cr" for consolidated (different accounting basis).</p>
          <p style={{ margin: '0 0 4px' }}><b>Reconciliation:</b> Branches disagree on which figure applies. Agreement score = 0.5. Confidence drops.</p>
          <p style={{ margin: '0', color: '#856404', fontWeight: 600 }}>→ Result: Routes to officer review. Shows BOTH interpretations. Officer decides which applies.</p>
        </div>
      </S>

      <S id="mosaic" title="Confidence Mosaic (Harmonic Mean)">
        <p><b>Why harmonic mean:</b> One weak component pulls the total down. A cell with 95% OCR but 0% extraction = low composite. This is intentional — it surfaces the weakest link.</p>
        <table className="govt-table"><thead><tr><th>Component</th><th>Measures</th><th>When it's low</th></tr></thead><tbody>
          <tr><td>OCR Quality</td><td>How well we read the source page</td><td>Blurry scan, stamp overlap, tilt</td></tr>
          <tr><td>Field Extraction</td><td>Did we find the specific value?</td><td>Value not in the document</td></tr>
          <tr><td>Entity Match</td><td>Bidder name consistency across docs</td><td>Name mismatch = fraud signal</td></tr>
          <tr><td>Rules Branch</td><td>Regex pattern confidence</td><td>No pattern matched</td></tr>
          <tr><td>LLM Branch</td><td>Claude's extraction confidence</td><td>LLM errored or uncertain</td></tr>
        </tbody></table>
        <p><b>Formula:</b> Composite = N / (1/c₁ + 1/c₂ + ... + 1/cₙ) where cᵢ are non-zero components.</p>
      </S>

      <S id="dissent" title="Devil's Advocate (Adversarial Review)">
        <p><b>What:</b> A second Claude call that argues AGAINST whatever verdict the primary pipeline produced.</p>
        <p><b>Why:</b> Prevents confirmation bias. If the dissent raises a genuine doubt (severity=high), the cell routes to mandatory_review.</p>
        <p><b>How:</b> Prompt: "You are a senior officer who disagrees with this verdict. Find the strongest argument against it."</p>
        <p><b>Output:</b> Dissent text + severity (low/medium/high) + suggested check + alternative verdict.</p>
      </S>

      <S id="statistical" title="Statistical Fraud Detection">
        <p><b>Three peer-reviewed techniques applied to every tender:</b></p>
        <table className="govt-table"><thead><tr><th>Technique</th><th>What it detects</th><th>How it works</th><th>Reference</th></tr></thead><tbody>
          <tr><td><b>Benford's Law</b></td><td>Fabricated financial figures</td><td>χ² test on first-digit distribution. Natural financial data: digit 1 appears ~30% of the time, digit 9 appears ~5%. Fabricated data tends toward uniform distribution.</td><td>Nigrini 1996</td></tr>
          <tr><td><b>Z-score Pooling</b></td><td>Inflated/underbid values</td><td>Per-criterion: compute pool mean + σ across all bidders. Flag any bidder &gt;1.5σ from mean.</td><td>OECD 2012</td></tr>
          <tr><td><b>Bid-spread CV</b></td><td>Price-fixing / cover bidding</td><td>Coefficient of Variation across all bids. CV &lt; 0.05 = suspiciously uniform (coordinated). CV &gt; 0.8 = one real bid + inflated dummies.</td><td>Bajari & Ye 2003</td></tr>
        </tbody></table>
        <div style={{ background: '#f8f9fa', border: '1px solid var(--line)', borderRadius: '3px', padding: '12px', margin: '12px 0' }}>
          <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Real example — Benford's Law in action:</p>
          <p style={{ margin: '0 0 4px' }}>Tender has 4 bidders, each submitting 3 years of turnover + net worth + project values = ~20 financial figures total.</p>
          <p style={{ margin: '0 0 4px' }}>System collects all 20 first digits. Expected (Benford): 1→30%, 2→18%, 3→12%...</p>
          <p style={{ margin: '0 0 4px' }}>If observed: 1→15%, 5→25%, 7→20% → χ² = 28.4 (threshold 15.5) → <b>FLAGGED</b>.</p>
          <p style={{ margin: '0', fontSize: '11px', color: 'var(--ink-soft)' }}>This catches bidders who "round" their figures to look impressive (₹150 Cr, ₹500 Cr, ₹75 Cr) — natural accounting data rarely has this pattern.</p>
        </div>
        <div style={{ background: '#f8f9fa', border: '1px solid var(--line)', borderRadius: '3px', padding: '12px', margin: '12px 0' }}>
          <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Real example — Sequential DD detection (CCI 2025 signal):</p>
          <p style={{ margin: '0 0 4px' }}>Bidder A submits EMD DD No. 845221. Bidder B submits DD No. 845222. Gap = 1.</p>
          <p style={{ margin: '0 0 4px' }}>This means both DDs were issued by the same bank teller within minutes of each other.</p>
          <p style={{ margin: '0', fontSize: '11px', color: 'var(--ink-soft)' }}>The Competition Commission of India cited this exact pattern in multiple 2024-25 cartel orders. Our system catches it automatically.</p>
        </div>
      </S>

      <S id="entity" title="Entity Resolution (Shell Company Detection)">
        <p><b>What:</b> Detect the same entity bidding under variant names (e.g., "Acme Defence Mfg Pvt Ltd" and "Acme Defence Manufacturing Private Limited").</p>
        <p><b>How:</b> Jaccard similarity on normalized word-sets after: (1) removing suffixes (Pvt Ltd, Limited, LLP), (2) expanding abbreviations (Mfg→Manufacturing, Engg→Engineering), (3) removing punctuation.</p>
        <p><b>Threshold:</b> Jaccard ≥ 0.6 = flagged as potential shell-company pair.</p>
        <p><b>Reference:</b> Fellegi & Sunter 1969; Christen 2012.</p>
      </S>

      <S id="security-scan" title="Document Security Scanning">
        <p><b>Runs on every upload BEFORE the AI sees the text.</b> Four checks:</p>
        <table className="govt-table"><thead><tr><th>Check</th><th>What it catches</th><th>How</th></tr></thead><tbody>
          <tr><td>Prompt injection</td><td>Adversarial text targeting LLM</td><td>12 regex patterns ("ignore previous instructions", etc.)</td></tr>
          <tr><td>Hidden text layers</td><td>Invisible text behind images (forged scans)</td><td>Compare native PDF text vs OCR output. Ratio &gt;3x = hidden layer.</td></tr>
          <tr><td>Metadata consistency</td><td>Tampered documents</td><td>Creation date in future, modification before creation.</td></tr>
          <tr><td>PDF structure</td><td>Malware vectors</td><td>Scan for /JavaScript, /Launch, /SubmitForm, /EmbeddedFile in raw bytes.</td></tr>
        </tbody></table>
      </S>

      <S id="hash-chain" title="Hash Chain Audit (Tamper-Proof)">
        <p><b>Mechanism:</b> Each audit_events row: entry_hash = SHA-256(prev_hash ‖ event_type ‖ event_data ‖ actor ‖ timestamp).</p>
        <p><b>Enforcement:</b> SQLite triggers block UPDATE and DELETE on audit_events. Attempting either raises ABORT.</p>
        <p><b>Verification:</b> Walk every row, recompute hash, compare. One tampered row breaks the chain.</p>
        <p><b>Genesis:</b> First row's prev_hash = 64 zeros. Every subsequent row links to the previous.</p>
      </S>

      <S id="verifier-arch" title="Verifier Architecture (Driver-Stub Pattern)">
        <p><b>Interface:</b> Every verifier implements: <code>verify(claim: dict) → VerificationResult(status, confidence, source_url, snapshot, sha256, notes)</code></p>
        <p><b>Two implementations per verifier:</b></p>
        <ol>
          <li><b>Stub:</b> Deterministic result based on format/logic. Returns <code>verified_via: "stub"</code>. Used in demo.</li>
          <li><b>Live:</b> Real HTTP call to the authority portal. Returns <code>verified_via: "live"</code>. One env flag to switch.</li>
        </ol>
        <p><b>Why stubs are a feature:</b> Live APIs are rate-limited, flaky, and unavailable offline. Stubs prove the architecture works. Switching to live = zero code change.</p>
      </S>

      <S id="stack" title="Technology Stack">
        <table className="govt-table"><thead><tr><th>Layer</th><th>Choice</th><th>Why this, not alternatives</th></tr></thead><tbody>
          <tr><td>AI</td><td>AWS Bedrock — Claude Sonnet 4.5</td><td>Single-cloud sovereignty. No data to Google/OpenAI/Azure. Cross-region inference profile.</td></tr>
          <tr><td>OCR</td><td>Bedrock Vision (primary) + Tesseract (fallback)</td><td>Same model reads AND reasons. No OCR→LLM gap. Tesseract for offline/degraded mode.</td></tr>
          <tr><td>Backend</td><td>Python 3.12 + FastAPI</td><td>Async-capable. 102 endpoints. Type-safe with Pydantic.</td></tr>
          <tr><td>Database</td><td>SQLite (WAL mode)</td><td>Single-file. Portable. No server dependency. Append-only triggers work natively.</td></tr>
          <tr><td>Frontend</td><td>React 18 + TypeScript + Vite</td><td>Type-safe. Fast HMR. Government-grade accessible UI.</td></tr>
          <tr><td>Testing</td><td>Playwright E2E + Python unit</td><td>Real browser interactions. Catches form-submit crashes, not just renders.</td></tr>
        </tbody></table>
      </S>

      <S id="sovereignty" title="Data Sovereignty">
        <p><b>One cloud. One model. One audit chain.</b></p>
        <ul>
          <li>AWS account 316394832518, region us-east-1.</li>
          <li>Only Bedrock API calls leave the machine (prompt + response).</li>
          <li>Source documents are NEVER sent to the model — only extracted text and rendered page images.</li>
          <li>No third-party AI services. No external document processing APIs. No cloud databases.</li>
        </ul>
        <p><b>Why this matters for CRPF:</b> Tender documents contain classified procurement details — quantities, specifications, pricing of defence equipment. Sending these to multiple external AI services creates data-sovereignty risk. Our architecture ensures all processing stays within a single controlled AWS environment.</p>
        <Info>The entire system can run air-gapped with a local model endpoint. The architecture doesn't depend on internet connectivity beyond the single Bedrock API call.</Info>
      </S>

      <S id="limitations" title="Honest Limitations">
        <p><b>What we name before the panel asks:</b></p>
        <table className="govt-table"><thead><tr><th>Limitation</th><th>Why it exists</th><th>Path to fix</th></tr></thead><tbody>
          <tr><td>Verifiers run in stub mode</td><td>Live APIs are rate-limited + flaky in demo</td><td>One env flag per verifier. Zero code change.</td></tr>
          <tr><td>Officer auth is a header shim</td><td>No SSO in hackathon scope</td><td>Replace with e-Office SSO. Audit chain already captures officer-ID.</td></tr>
          <tr><td>No PKCS#7/DSC on TEC PDF</td><td>Requires officer's private key infrastructure</td><td>Sign with officer's public key on finalise. Fields exist.</td></tr>
          <tr><td>Reproduce script verifies archive, not LLM re-run</td><td>LLM output is non-deterministic</td><td>Prompt-hash caching gives practical reproducibility.</td></tr>
          <tr><td>Debarment registry is local-seeded</td><td>No live CVC/GeM feed in demo</td><td>Cron job pulling monthly from cvc.gov.in.</td></tr>
        </tbody></table>
        <p><b>Philosophy:</b> Name the gap. Show the architecture handles it. Demonstrate the switch is one config change.</p>
      </S>

      <S id="metrics" title="System Metrics">
        <table className="govt-table"><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>
          <tr><td>API endpoints</td><td>102</td></tr>
          <tr><td>Database tables</td><td>31</td></tr>
          <tr><td>Anomaly detection techniques</td><td>18</td></tr>
          <tr><td>Audit event types</td><td>30+</td></tr>
          <tr><td>External verifier drivers</td><td>7</td></tr>
          <tr><td>Pipeline layers</td><td>5</td></tr>
          <tr><td>Prompt templates (versioned)</td><td>12</td></tr>
          <tr><td>Frontend components</td><td>22+</td></tr>
          <tr><td>E2E test cases</td><td>25</td></tr>
          <tr><td>Lines of Python (backend)</td><td>~8,000</td></tr>
          <tr><td>Lines of TypeScript (frontend)</td><td>~6,000</td></tr>
        </tbody></table>
      </S>
    </div>
  );
}

// ─── Shared components ──────────────────────────────────────────────

function S({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} style={{ marginBottom: '28px' }}>
      <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--primary)', borderBottom: '2px solid var(--primary)', paddingBottom: '4px', marginBottom: '10px' }}>
        {title}
      </h3>
      {children}
    </section>
  );
}

function Info({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: '#e3f2fd', border: '1px solid #1565c0', borderRadius: '3px', padding: '8px 12px', margin: '8px 0', fontSize: '12px', color: '#0d47a1' }}>
      ℹ️ {children}
    </div>
  );
}

function Warn({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: '#fff3e0', border: '1px solid #e65100', borderRadius: '3px', padding: '8px 12px', margin: '8px 0', fontSize: '12px', color: '#bf360c' }}>
      ⚠️ {children}
    </div>
  );
}

function ModuleBox({ color, bg, title, items }: { color: string; bg: string; title: string; items: string[] }) {
  return (
    <div style={{ background: bg, border: `2px solid ${color}`, borderRadius: '3px', padding: '8px 10px' }}>
      <div style={{ fontSize: '10px', fontWeight: 700, color, marginBottom: '4px' }}>{title}</div>
      {items.map((item, i) => (
        <div key={i} style={{ fontSize: '10px', color: '#333', lineHeight: 1.4 }}>• {item}</div>
      ))}
    </div>
  );
}
