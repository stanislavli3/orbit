import { AuthenticateWithRedirectCallback } from '@clerk/clerk-react';

export function SsoCallbackPage() {
  return <AuthenticateWithRedirectCallback />;
}
