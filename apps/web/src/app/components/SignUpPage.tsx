import { SignUp } from '@clerk/clerk-react';

export function SignUpPage() {
  return (
    <div className="w-full h-screen flex items-center justify-center bg-[#F7F7F7]">
      <SignUp routing="path" path="/sign-up" />
    </div>
  );
}
