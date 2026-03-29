import { useState } from 'react';
import { useSignIn } from '@clerk/clerk-react';

function OrbitLogo() {
  return (
    <div className="w-9 h-9 bg-[#111111] rounded-lg flex items-center justify-center shrink-0">
      <span className="text-white text-sm font-bold tracking-tight">O</span>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M17.64 9.20455C17.64 8.56637 17.5827 7.95273 17.4764 7.36364H9V10.845H13.8436C13.635 11.9700 13.0009 12.9232 12.0477 13.5614V15.8195H14.9564C16.6582 14.2527 17.64 11.9455 17.64 9.20455Z" fill="#4285F4"/>
      <path d="M9 18C11.43 18 13.4673 17.1941 14.9564 15.8195L12.0477 13.5614C11.2418 14.1014 10.2109 14.4204 9 14.4204C6.65591 14.4204 4.67182 12.8373 3.96409 10.71H0.957275V13.0418C2.43818 15.9832 5.48182 18 9 18Z" fill="#34A853"/>
      <path d="M3.96409 10.71C3.78409 10.17 3.68182 9.59318 3.68182 9C3.68182 8.40682 3.78409 7.83 3.96409 7.29V4.95818H0.957275C0.347727 6.17318 0 7.54773 0 9C0 10.4523 0.347727 11.8268 0.957275 13.0418L3.96409 10.71Z" fill="#FBBC05"/>
      <path d="M9 3.57955C10.3214 3.57955 11.5077 4.03364 12.4405 4.92545L15.0218 2.34409C13.4632 0.891818 11.4259 0 9 0C5.48182 0 2.43818 2.01682 0.957275 4.95818L3.96409 7.29C4.67182 5.16273 6.65591 3.57955 9 3.57955Z" fill="#EA4335"/>
    </svg>
  );
}

export function SignInPage() {
  const { signIn, isLoaded } = useSignIn();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [emailSent, setEmailSent] = useState(false);
  const [error, setError] = useState('');

  const handleGoogleSignIn = async () => {
    if (googleLoading) return;
    setError('');
    setGoogleLoading(true);
    if (!isLoaded || !signIn) {
      setError('Clerk not ready — please refresh the page.');
      setGoogleLoading(false);
      return;
    }
    try {
      await signIn.authenticateWithRedirect({
        strategy: 'oauth_google',
        redirectUrl: `${window.location.origin}/sso-callback`,
        redirectUrlComplete: `${window.location.origin}/`,
      });
    } catch (err: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const clerkErr = err as any;
      const msg = clerkErr?.errors?.[0]?.longMessage
        ?? clerkErr?.errors?.[0]?.message
        ?? (err instanceof Error ? err.message : 'Something went wrong. Please try again.');
      setError(msg);
      setGoogleLoading(false);
    }
  };

  const handleEmailSignIn = async () => {
    if (!isLoaded || !email.trim()) return;
    setLoading(true);
    setError('');
    try {
      await signIn.create({
        strategy: 'email_link',
        identifier: email.trim(),
        redirectUrl: window.location.origin + '/',
      });
      setEmailSent(true);
    } catch (err: unknown) {
      const clerkErr = err as { errors?: Array<{ longMessage?: string; message?: string }> };
      const msg = clerkErr?.errors?.[0]?.longMessage
        ?? clerkErr?.errors?.[0]?.message
        ?? (err instanceof Error ? err.message : 'Could not send magic link. Please try Google sign-in.');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full h-screen flex bg-[#F7F7F7]">
      {/* Left panel — branding / decorative */}
      <div className="hidden lg:flex lg:w-[52%] bg-[#111111] flex-col justify-between p-12 relative overflow-hidden">
        {/* Subtle grid pattern */}
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
        />

        {/* Decorative circle blobs */}
        <div className="absolute -bottom-32 -left-32 w-[480px] h-[480px] rounded-full bg-white opacity-[0.03]" />
        <div className="absolute top-24 right-[-80px] w-[320px] h-[320px] rounded-full bg-white opacity-[0.03]" />

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-8 h-8 bg-white rounded-md flex items-center justify-center">
            <span className="text-[#111111] text-sm font-bold tracking-tight">O</span>
          </div>
          <span className="text-white text-base font-semibold tracking-tight">Orbit</span>
        </div>

        {/* Center copy */}
        <div className="relative z-10 space-y-6">
          <div className="space-y-3">
            <p className="text-[#6B7280] text-xs uppercase tracking-widest font-medium">Engineering Intelligence</p>
            <h1 className="text-white text-[2.6rem] leading-[1.15] font-semibold tracking-tight">
              Your engineering<br />files, understood.
            </h1>
          </div>
          <p className="text-[#9CA3AF] text-sm leading-relaxed max-w-xs">
            Analyze CAD files, extract metadata, and generate insights across your entire project vault.
          </p>

          {/* Feature pills */}
          <div className="flex flex-col gap-2 pt-2">
            {[
              'Analyze drawing sets',
              'Generate JSON profiles',
              'Identify design patterns',
              'Search for similar parts',
            ].map((feature) => (
              <div key={feature} className="flex items-center gap-2.5">
                <div className="w-1 h-1 rounded-full bg-[#4B5563]" />
                <span className="text-[#6B7280] text-sm">{feature}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom tagline */}
        <div className="relative z-10">
          <p className="text-[#374151] text-xs">Built for engineers who ship.</p>
        </div>
      </div>

      {/* Right panel — sign-in form */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 relative">
        {/* Mobile logo */}
        <div className="lg:hidden absolute top-8 left-8 flex items-center gap-2.5">
          <OrbitLogo />
          <span className="text-[#111111] text-base font-semibold tracking-tight">Orbit</span>
        </div>

        <div className="w-full max-w-[360px] space-y-8">
          {/* Header */}
          <div className="space-y-2">
            <h2 className="text-[#111111] text-2xl font-semibold tracking-tight">Sign in to Orbit</h2>
            <p className="text-[#6B7280] text-sm">
              Access your engineering vault and AI assistant.
            </p>
          </div>

          {/* Google sign-in button */}
          <div className="space-y-3">
            {error && (
              <p className="text-sm text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] rounded-lg px-4 py-3">
                {error}
              </p>
            )}
            <button
              onClick={handleGoogleSignIn}
              disabled={googleLoading}
              className="w-full flex items-center justify-center gap-3 px-4 py-2.5 bg-white border border-[#E6E6E6] rounded-lg text-[#111111] text-sm font-medium hover:bg-[#F7F7F7] hover:border-[#D1D5DB] active:bg-[#F0F0F0] disabled:opacity-60 disabled:cursor-not-allowed transition-all duration-150 shadow-[0_1px_2px_rgba(0,0,0,0.05)]"
            >
              {googleLoading ? (
                <svg className="animate-spin w-[18px] h-[18px] text-[#6B7280]" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              ) : (
                <GoogleIcon />
              )}
              {googleLoading ? 'Redirecting to Google...' : 'Continue with Google'}
            </button>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-[#E6E6E6]" />
            <span className="text-[#9CA3AF] text-xs">or</span>
            <div className="flex-1 h-px bg-[#E6E6E6]" />
          </div>

          {/* Email field */}
          <div className="space-y-3">
            {emailSent ? (
              <p className="text-sm text-[#111111] bg-[#F4F4F4] rounded-lg px-4 py-3">
                Check your inbox — we sent a magic link to <strong>{email}</strong>.
              </p>
            ) : (
              <>
                <div className="space-y-1.5">
                  <label className="text-[#374151] text-xs font-medium">Work email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleEmailSignIn()}
                    placeholder="you@company.com"
                    className="w-full px-3 py-2.5 bg-white border border-[#E6E6E6] rounded-lg text-sm text-[#111111] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] transition-all duration-150"
                  />
                </div>

                <button
                  onClick={handleEmailSignIn}
                  disabled={loading || !email.trim()}
                  className="w-full px-4 py-2.5 bg-[#111111] text-white text-sm font-medium rounded-lg hover:bg-[#1F1F1F] active:bg-[#333333] disabled:opacity-50 transition-colors duration-150"
                >
                  {loading ? 'Sending...' : 'Continue with email'}
                </button>
              </>
            )}
          </div>

          {/* Footer */}
          <p className="text-[#9CA3AF] text-xs text-center leading-relaxed">
            By continuing, you agree to Orbit's{' '}
            <a href="#" className="text-[#6B7280] underline underline-offset-2 hover:text-[#111111] transition-colors">
              Terms of Service
            </a>{' '}
            and{' '}
            <a href="#" className="text-[#6B7280] underline underline-offset-2 hover:text-[#111111] transition-colors">
              Privacy Policy
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
