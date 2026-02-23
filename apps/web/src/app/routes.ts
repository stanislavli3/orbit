import { createBrowserRouter } from 'react-router';
import Root from './Root';
import { AssistantPage } from './components/AssistantPage';
import { VaultPage } from './components/VaultPage';
import { HistoryPage } from './components/HistoryPage';
import { ProjectDetailPage } from './components/ProjectDetailPage';

export const router = createBrowserRouter([
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