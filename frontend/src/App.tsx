// App router. Single layout, top routes (dashboard, new tender, inbox,
// help, audit-log, settings), then the Tender Space ("dossier") which
// fans out into 5 step views + 3 utility tabs.

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import { ToastProvider } from './components/Toast';
import Dashboard from './pages/Dashboard';
import NewTender from './pages/NewTender';
import Inbox from './pages/Inbox';
import Help from './pages/Help';
import AuditLog from './pages/AuditLog';
import Settings from './pages/Settings';
import TenderSpace from './pages/TenderSpace';

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tenders/new" element={<NewTender />} />
            <Route path="/queue" element={<Inbox />} />
            <Route path="/help" element={<Help />} />
            <Route path="/audit-log" element={<AuditLog />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/tenders/:id" element={<Navigate to="setup" replace />} />
            <Route path="/tenders/:id/setup"      element={<TenderSpace step="setup" />} />
            <Route path="/tenders/:id/documents"  element={<TenderSpace step="documents" />} />
            <Route path="/tenders/:id/criteria"   element={<TenderSpace step="criteria" />} />
            <Route path="/tenders/:id/evaluation" element={<TenderSpace step="evaluation" />} />
            <Route path="/tenders/:id/report"     element={<TenderSpace step="report" />} />
            <Route path="/tenders/:id/file-vault" element={<TenderSpace step="file-vault" />} />
            <Route path="/tenders/:id/verifiers"  element={<TenderSpace step="verifiers" />} />
            <Route path="/tenders/:id/audit"      element={<TenderSpace step="audit" />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </ToastProvider>
    </BrowserRouter>
  );
}
