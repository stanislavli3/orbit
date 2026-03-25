import { Outlet } from 'react-router';
import { SignedIn, SignedOut, RedirectToSignIn } from '@clerk/clerk-react';
import { AppSidebar } from './components/AppSidebar';

export default function Root() {
  return (
    <>
      <SignedIn>
        <div className="w-full h-screen flex bg-[#F7F7F7]">
          <AppSidebar />
          <Outlet />
        </div>
      </SignedIn>
      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
    </>
  );
}
