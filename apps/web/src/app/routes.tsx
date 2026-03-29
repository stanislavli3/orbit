import { createBrowserRouter } from 'react-router';
import Root from './Root';
import { AssistantPage } from './components/AssistantPage';
import { VaultPage } from './components/VaultPage';
import { HistoryPage } from './components/HistoryPage';
import { ProjectDetailPage } from './components/ProjectDetailPage';
import { ComingSoonPage } from './components/ComingSoonPage';
import { FileResultPage } from './components/FileResultPage';
import { SignInPage } from './components/SignInPage';
import { SsoCallbackPage } from './components/SsoCallbackPage';

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
      { index: true, Component: AssistantPage },
      { path: 'assistant', Component: AssistantPage },
      { path: 'vault', Component: VaultPage },
      { path: 'project/:id', Component: ProjectDetailPage },
      { path: 'project/:id/file/:fileId/result', Component: FileResultPage },
      { path: 'extraction-runs', element: <ComingSoonPage title="Extraction Runs" subtitle="Batch extraction jobs and their status." /> },
      { path: 'workflows', element: <ComingSoonPage title="Workflows" subtitle="Automate extraction pipelines across your projects." /> },
      { path: 'history', Component: HistoryPage },
      { path: 'library', element: <ComingSoonPage title="Library" subtitle="Reusable extraction profiles and knowledge bases." /> },
      { path: 'settings', element: <ComingSoonPage title="Settings" subtitle="Manage your profile, API keys, and preferences." /> },
    ],
  },
]);
