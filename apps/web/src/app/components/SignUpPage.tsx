import { SignUp } from '@clerk/clerk-react';

export function SignUpPage() {
  return (
    <div className="w-full h-screen flex items-center justify-center bg-[#FAF7F2]">
      <SignUp routing="path" path="/sign-up" />
    </div>
  );
}
