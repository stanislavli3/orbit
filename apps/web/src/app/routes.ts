import { createBrowserRouter } from 'react-router';
import Root from './Root';
import { AssistantPage } from './components/AssistantPage';
import { VaultPage } from './components/VaultPage';
import { HistoryPage } from './components/HistoryPage';
import { ProjectDetailPage } from './components/ProjectDetailPage';
import { SignInPage } from './components/SignInPage';
import { SignUpPage } from './components/SignUpPage';

export const router = createBrowserRouter([
  // Auth pages — outside Root so they render without the sidebar
  { path: '/sign-in/*', Component: SignInPage },
  { path: '/sign-up/*', Component: SignUpPage },
  {
    path: '/',
    Component: Root,
    children: [
      { index: true, Component: AssistantPage },
      { path: 'assistant', Component: AssistantPage },
      { path: 'vault', Component: VaultPage },
      { path: 'project/:id', Component: ProjectDetailPage },
      { path: 'extraction-runs', Component: VaultPage }, // Placeholder
      { path: 'workflows', Component: VaultPage }, // Placeholder
      { path: 'history', Component: HistoryPage },
      { path: 'library', Component: VaultPage }, // Placeholder
      { path: 'settings', Component: VaultPage }, // Placeholder
    ],
  },
]);