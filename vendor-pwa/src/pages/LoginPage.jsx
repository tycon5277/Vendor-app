import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Storefront } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { useAuthStore } from '../store/authStore';

export default function LoginPage() {
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [step, setStep] = useState('phone');
  const { sendOTP, verifyOTP, isLoading, error, isAuthenticated, clearError } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) navigate('/');
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    clearError();
  }, [step, clearError]);

  const handleSendOTP = async (e) => {
    e.preventDefault();
    if (phone.length < 10) return;
    const result = await sendOTP(phone);
    if (result.success) {
      setOtp('');
      setStep('otp');
      toast.success('OTP sent to your phone');
    }
  };

  const handleVerifyOTP = async (e) => {
    e.preventDefault();
    if (otp.length < 4) return;
    const result = await verifyOTP(phone, otp);
    if (result.success) {
      toast.success('Welcome back!');
      navigate('/');
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFDFD] flex" data-testid="login-page">
      {/* Left side - Brand */}
      <div className="hidden lg:flex lg:w-1/2 bg-[#002FA7] p-12 flex-col justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-white rounded flex items-center justify-center">
            <Storefront size={28} weight="bold" className="text-[#002FA7]" />
          </div>
          <div>
            <h1 className="text-white text-2xl font-bold" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
              QuickWish
            </h1>
            <span className="text-white/70 text-sm uppercase tracking-wider">Vendor Portal</span>
          </div>
        </div>

        <div>
          <h2 className="text-white text-4xl font-bold mb-4" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
            Manage your shop,<br />grow your business.
          </h2>
          <p className="text-white/80 text-lg">
            Accept orders, manage products, track earnings — all in one place.
          </p>
        </div>

        <div className="text-white/60 text-sm">© 2026 QuickWish. All rights reserved.</div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8 flex items-center gap-3">
            <div className="w-12 h-12 bg-[#002FA7] rounded flex items-center justify-center">
              <Storefront size={28} weight="bold" className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>QuickWish</h1>
              <span className="text-[#52525B] text-xs uppercase tracking-wider">Vendor Portal</span>
            </div>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold mb-2" style={{ fontFamily: 'Cabinet Grotesk, system-ui' }}>
              {step === 'phone' ? 'Sign in to your shop' : 'Enter verification code'}
            </h2>
            <p className="text-[#52525B]">
              {step === 'phone'
                ? 'Enter your registered phone number to continue'
                : `We sent a code to +91 ${phone}`}
            </p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded text-sm text-red-700" data-testid="login-error-message">
              {error}
            </div>
          )}

          {step === 'phone' ? (
            <form onSubmit={handleSendOTP}>
              <div className="mb-6">
                <label className="label">Phone Number</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#52525B]">+91</span>
                  <input
                    type="tel"
                    inputMode="numeric"
                    autoComplete="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 10))}
                    placeholder="Enter 10-digit number"
                    className="input h-12"
                    style={{ paddingLeft: '3rem' }}
                    autoFocus
                    data-testid="login-phone-input"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={phone.length < 10 || isLoading}
                className="btn btn-primary w-full h-12 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="login-send-otp-button"
              >
                {isLoading ? <span className="spinner" /> : (<>Continue <ArrowRight size={20} weight="bold" /></>)}
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerifyOTP}>
              <div className="mb-6">
                <label className="label">Verification Code</label>
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="Enter 6-digit OTP"
                  className="input text-center text-2xl tracking-[0.5em] h-14"
                  autoFocus
                  data-testid="login-otp-input"
                />
              </div>

              <button
                type="submit"
                disabled={otp.length < 4 || isLoading}
                className="btn btn-primary w-full h-12 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="login-verify-otp-button"
              >
                {isLoading ? <span className="spinner" /> : (<>Verify & Sign In <ArrowRight size={20} weight="bold" /></>)}
              </button>

              <button
                type="button"
                onClick={() => setStep('phone')}
                className="btn btn-outline w-full h-12 mt-3"
                data-testid="login-change-phone-button"
              >
                Change Phone Number
              </button>
            </form>
          )}

          <p className="mt-8 text-center text-sm text-[#52525B]">
            By continuing, you agree to our Terms of Service and Privacy Policy.
          </p>
        </div>
      </div>
    </div>
  );
}
