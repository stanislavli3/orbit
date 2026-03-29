import { Outlet } from 'react-router';
import { SignedIn, SignedOut, RedirectToSignIn } from '@clerk/clerk-react';
import { AppSidebar } from './components/AppSidebar';
import { Toaster } from 'sonner';

export default function Root() {
  return (
    <>
      <SignedIn>
        <div className="w-full h-screen flex bg-[#F7F7F7]">
          <AppSidebar />
          <Outlet />
          <Toaster position="top-center" richColors />
        </div>
      </SignedIn>
      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
    </>
  );
}
