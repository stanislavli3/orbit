import { SignIn } from '@clerk/clerk-react';

export function SignInPage() {
  return (
    <div className="w-full h-screen flex items-center justify-center bg-[#F7F7F7]">
      <SignIn routing="path" path="/sign-in" />
    </div>
  );
}
