import { createBrowserRouter, useSearchParams } from 'react-router';
import Root from './Root';
import { AssistantPage } from './components/AssistantPage';
import { VaultPage } from './components/VaultPage';
import { HistoryPage } from './components/HistoryPage';
import { ProjectDetailPage } from './components/ProjectDetailPage';
import { SettingsPage } from './components/SettingsPage';
import { LibraryPage } from './components/LibraryPage';
import { ExtractionRunsPage } from './components/ExtractionRunsPage';
import { BomAgentPage } from './components/BomAgentPage';
import { BomRunPage } from './components/BomRunPage';
import { BomAnalyticsPage } from './components/BomAnalyticsPage';
import { ProjectAnalyticsPage } from './components/ProjectAnalyticsPage';
import { FileResultPage } from './components/FileResultPage';
import { SignInPage } from './components/SignInPage';
import { SsoCallbackPage } from './components/SsoCallbackPage';

function AssistantWrapper() {
  const [searchParams] = useSearchParams();
  const session = searchParams.get('session');
  const t = searchParams.get('t');
  // session param loads an existing chat; t param (timestamp) forces a fresh mount
  const mountKey = session ?? t ?? 'new';
  return <AssistantPage key={mountKey} initialSessionId={session} />;
}

export const router = createBrowserRouter([
  {
    path: '/signin',
    Component: SignInPage,
  },
  {
    path: '/sso-callback',
    Component: SsoCallbackPage,
  },
  {
    path: '/',
    Component: Root,
    children: [
      { index: true, Component: AssistantWrapper },
      { path: 'assistant', Component: AssistantWrapper },
      { path: 'vault', Component: VaultPage },
      { path: 'project/:id', Component: ProjectDetailPage },
      { path: 'project/:id/analytics', Component: ProjectAnalyticsPage },
      { path: 'project/:id/file/:fileId/result', Component: FileResultPage },
      { path: 'extraction-runs', Component: ExtractionRunsPage },
      { path: 'bom', Component: BomAgentPage },
      { path: 'bom/:id', Component: BomRunPage },
      { path: 'bom/:id/analytics', Component: BomAnalyticsPage },
      { path: 'workflows', Component: VaultPage }, // Placeholder
      { path: 'history', Component: HistoryPage },
      { path: 'library', Component: LibraryPage },
      { path: 'settings', Component: SettingsPage },
    ],
  },
]);
