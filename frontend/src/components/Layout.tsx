// App shell — CRPF Government Portal layout (exact match).
// Horizontal nav is PRIMARY. Sidebar only appears INSIDE a dossier
// (contextual sub-menu, like CRPF's "Provisioning" sidebar).

import { ReactNode, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import OfficerPicker from './OfficerPicker';
import AccessibilityBar from './AccessibilityBar';
import InboxBadge from './InboxBadge';
import CopilotPanel from './CopilotPanel';

const NAV_ITEMS = [
  { to: '/', label: 'Home', exact: true },
  { to: '/tenders/new', label: 'New Evaluation', exact: true },
  { to: '/queue', label: 'Review Queue', exact: true },
  { to: '/help', label: 'Help & Manual', exact: true },
  { to: '/audit-log', label: 'Audit Trail', exact: true },
  { to: '/settings', label: 'Settings', exact: true },
];

// Sidebar items — only shown inside a dossier
const DOSSIER_SIDEBAR = [
  { to: 'setup', label: 'Overview' },
  { to: 'documents', label: 'Documents' },
  { to: 'criteria', label: 'Criteria' },
  { to: 'evaluation', label: 'Evaluation Matrix' },
  { to: 'report', label: 'TEC Report' },
  { to: 'file-vault', label: 'File Vault' },
  { to: 'verifiers', label: 'External Verifiers' },
  { to: 'audit', label: 'Audit Chain' },
];

export default function Layout({ children }: { children: ReactNode }) {
  const loc = useLocation();

  // Detect if we're inside a tender dossier
  const tenderMatch = loc.pathname.match(/^\/tenders\/([^\/]+)(?:\/(.+))?/);
  const tenderId = tenderMatch?.[1];
  const tenderStep = tenderMatch?.[2] || 'setup';
  const insideDossier = Boolean(tenderId) && tenderId !== 'new';
  const showCopilot = insideDossier;

  // Get page title for the banner
  const pageTitle = getPageTitle(loc.pathname);

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg)' }}>
      <a href="#main" className="skip-link">Skip to content</a>

      {/* ─── Top Blue Bar ─── */}
      <div className="govt-header">
        <span style={{ fontSize: '12px' }}>
          Welcome to VerdictAI — AI-Assisted Tender Evaluation System, CRPF
        </span>
        <div className="flex items-center gap-3">
          <AccessibilityBar />
          <OfficerPicker />
        </div>
      </div>

      {/* ─── Brand Header ─── */}
      <header className="brand-header">
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '12px', textDecoration: 'none' }}>
          {/* National Emblem (left) */}
          <img
            src="/assets/national-emblem.png"
            alt="National Emblem of India"
            style={{ height: '48px', width: 'auto' }}
          />
          <div className="brand-text">
            <span className="brand-hindi">केन्द्रीय रिजर्व पुलिस बल</span>
            <span className="brand-english">Central Reserve Police Force</span>
            <span style={{ fontSize: '10px', color: '#888', marginTop: '1px' }}>
              Directorate General — Procurement Cell
            </span>
          </div>
        </Link>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* VerdictAI Logo */}
          <div style={{ textAlign: 'right' }}>
            <span
              style={{
                fontFamily: "'Outfit', sans-serif",
                fontSize: '26px',
                fontWeight: 800,
                color: 'var(--primary)',
                letterSpacing: '-0.02em',
              }}
            >
              Verdict
              <span style={{ color: 'var(--accent)' }}>AI</span>
            </span>
            <div style={{ fontSize: '9px', color: '#999', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Sovereign Evidence Engine
            </div>
          </div>
        </div>
      </header>

      {/* ─── Navigation Bar ─── */}
      <nav className="nav-bar" aria-label="Main navigation">
        {NAV_ITEMS.map(item => {
          const active = item.exact
            ? loc.pathname === item.to
            : loc.pathname.startsWith(item.to);
          return (
            <Link key={item.to} to={item.to} className={active ? 'is-active' : ''}>
              {item.label}
              {item.to === '/queue' && <InboxBadge />}
            </Link>
          );
        })}
        {insideDossier && (
          <Link to={`/tenders/${tenderId}/evaluation`} className="is-active" style={{ marginLeft: '8px', borderLeft: '1px solid rgba(255,255,255,0.2)', paddingLeft: '16px' }}>
            📋 Active Dossier
          </Link>
        )}
      </nav>

      {/* ─── Page Banner (blue gradient) ─── */}
      {!insideDossier && (
        <div className="page-banner">
          <h1>{pageTitle}</h1>
          <div className="breadcrumb">
            <Link to="/">Home</Link> / {pageTitle}
          </div>
        </div>
      )}

      {/* ─── Body ─── */}
      <div className="flex flex-1 min-h-0">
        {/* Contextual Sidebar — only inside a dossier */}
        {insideDossier && (
          <aside
            className="sidebar-menu"
            style={{
              width: '220px',
              flexShrink: 0,
              margin: '16px 0 16px 16px',
              alignSelf: 'flex-start',
              position: 'sticky',
              top: '16px',
            }}
          >
            <h3>Dossier Menu</h3>
            {DOSSIER_SIDEBAR.map(item => (
              <Link
                key={item.to}
                to={`/tenders/${tenderId}/${item.to}`}
                className={`menu-item ${tenderStep === item.to ? 'is-active' : ''}`}
              >
                {item.label}
              </Link>
            ))}
          </aside>
        )}

        {/* Main Content */}
        <main
          id="main"
          className="flex-1 min-w-0 overflow-y-auto relative"
          style={{ minHeight: 'calc(100vh - 240px)', padding: insideDossier ? '16px 20px' : '24px 32px' }}
        >
          {children}
        </main>

        {/* Right Copilot Panel */}
        {showCopilot && tenderId && (
          <CollapsibleCopilot tenderId={tenderId} />
        )}
      </div>

      {/* ─── Footer ─── */}
      <footer className="govt-footer">
        <div style={{ marginBottom: '6px' }}>
          <a href="/help">Terms & Conditions</a> | <a href="/help">Privacy Policy</a> | <a href="/help">Accessibility Statement</a> | <a href="/help">Help</a>
        </div>
        <div>
          Built by <strong>Chanikya Nelapatla</strong> · Powered by AWS Bedrock · © 2026 VerdictAI
        </div>
      </footer>
    </div>
  );
}

function getPageTitle(pathname: string): string {
  if (pathname === '/') return 'Tender Evaluation Dashboard';
  if (pathname === '/tenders/new') return 'Create New Evaluation Dossier';
  if (pathname === '/queue') return 'Review Queue — Pending Decisions';
  if (pathname === '/help') return 'Help & Manual';
  if (pathname === '/audit-log') return 'Workspace Audit Trail';
  if (pathname === '/settings') return 'System Settings';
  return 'VerdictAI';
}

function CollapsibleCopilot({ tenderId }: { tenderId: string }) {
  const [open, setOpen] = useState(true);
  useEffect(() => {
    try { if (localStorage.getItem('verdictai.copilot-open') === '0') setOpen(false); } catch {}
  }, []);
  useEffect(() => {
    try { localStorage.setItem('verdictai.copilot-open', open ? '1' : '0'); } catch {}
  }, [open]);

  if (!open) {
    return (
      <button
        type="button"
        style={{
          width: '32px',
          background: 'var(--paper)',
          borderLeft: '1px solid var(--line)',
          color: 'var(--primary)',
          writingMode: 'vertical-rl',
          fontWeight: 600,
          fontSize: '11px',
          letterSpacing: '0.08em',
          cursor: 'pointer',
        }}
        onClick={() => setOpen(true)}
        aria-label="Show Copilot"
      >
        ‹ COPILOT
      </button>
    );
  }

  return (
    <aside
      className="app-copilot"
      style={{
        height: '100vh',
        maxHeight: '100vh',
        position: 'sticky',
        top: '0',
        alignSelf: 'flex-start',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div className="app-copilot-header">
        <span>AI Copilot</span>
        <button
          type="button"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-soft)' }}
          onClick={() => setOpen(false)}
          aria-label="Hide Copilot"
        >
          ›
        </button>
      </div>
      <div className="flex-1 min-h-0">
        <CopilotPanel tenderId={tenderId} />
      </div>
    </aside>
  );
}
