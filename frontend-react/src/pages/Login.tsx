import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Shield, Lock, User, AlertCircle, Loader2, ChevronDown, Key } from 'lucide-react';
import { supabase } from '../lib/supabase';
import { fetchApi } from '../api/client';

export const Login: React.FC = () => {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showDemoMenu, setShowDemoMenu] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const populateDemo = (username: string) => {
    setIdentifier(username);
    setPassword('NagarDrishti@Demo2026!');
    setShowDemoMenu(false);
  };

  const from = (location.state as any)?.from?.pathname || '/';

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      // Proxy through backend to resolve username/email and login
      const response = await fetchApi<{ access_token: string; refresh_token: string }>('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier, password }),
      });

      // Set the session locally using the tokens from the backend
      const { error: sessionError } = await supabase.auth.setSession({
        access_token: response.access_token,
        refresh_token: response.refresh_token,
      });

      if (sessionError) {
        throw sessionError;
      }

      navigate(from, { replace: true });
    } catch (err: any) {
      console.error('Login error:', err);
      setError(err.message || 'Invalid credentials. Please check your username/email and password.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex bg-[#0B1120] text-gray-100 font-sans selection:bg-blue-500/30">
      {/* Left side - Branding/Decorative */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-gradient-to-br from-blue-900/40 to-[#0B1120] border-r border-blue-900/30 overflow-hidden">
        {/* Animated grid background */}
        <div 
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage: `linear-gradient(rgba(59, 130, 246, 0.2) 1px, transparent 1px), linear-gradient(90deg, rgba(59, 130, 246, 0.2) 1px, transparent 1px)`,
            backgroundSize: '40px 40px',
            backgroundPosition: 'center center'
          }}
        />
        
        {/* Glowing orb */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-blue-500/10 rounded-full blur-[100px]" />
        
        <div className="relative z-10 p-12 flex flex-col justify-between h-full">
          <div className="flex items-center gap-3">
            <Shield className="w-10 h-10 text-blue-500" />
            <span className="text-2xl font-bold tracking-wider text-white">NagarDrishti</span>
          </div>
          
          <div className="space-y-6 max-w-lg">
            <h1 className="text-4xl font-bold leading-tight text-white">
              Urban Intelligence & Command Platform
            </h1>
            <p className="text-blue-200/60 text-lg leading-relaxed">
              Secure portal for monitoring urban infrastructure, intelligent traffic systems, and field maintenance operations.
            </p>
            <div className="pt-8 flex items-center gap-4 text-sm text-blue-300/40">
              <span className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                SYSTEMS ONLINE
              </span>
              <span>•</span>
              <span>v9.0.0</span>
            </div>
          </div>
        </div>
      </div>

      {/* Right side - Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8">
        <div className="w-full max-w-md space-y-8">
          <div className="text-center lg:hidden flex flex-col items-center gap-4 mb-12">
             <Shield className="w-12 h-12 text-blue-500" />
             <h2 className="text-3xl font-bold tracking-wider text-white">NagarDrishti</h2>
          </div>

          <div className="space-y-2 text-center lg:text-left">
            <h2 className="text-3xl font-bold text-white tracking-tight">Authorization Required</h2>
            <p className="text-gray-400 text-sm">Please enter your municipal credentials to continue.</p>
          </div>

          {error && (
            <div className="flex items-center gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm animate-in fade-in slide-in-from-top-2">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <p>{error}</p>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-6">
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-300 ml-1">Username or Email</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <User className="h-5 w-5 text-gray-500" />
                  </div>
                  <input
                    type="text"
                    required
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    className="block w-full pl-10 pr-3 py-3 bg-gray-900/50 border border-gray-700/50 rounded-lg focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all text-white placeholder-gray-500 sm:text-sm"
                    placeholder="officer.smith or smith@city.gov"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-300 ml-1">Password</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-gray-500" />
                  </div>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="block w-full pl-10 pr-3 py-3 bg-gray-900/50 border border-gray-700/50 rounded-lg focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all text-white placeholder-gray-500 sm:text-sm"
                    placeholder="••••••••"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading || !identifier || !password}
              className="w-full flex justify-center items-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 focus:ring-offset-gray-900 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  Authenticating...
                </>
              ) : (
                'SIGN IN'
              )}
            </button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-700/50" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-[#0B1120] text-gray-500">or</span>
            </div>
          </div>

          <div className="relative flex justify-center">
            <button
              type="button"
              onClick={() => setShowDemoMenu(!showDemoMenu)}
              className="flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-gray-800/50 hover:bg-gray-800 border border-gray-700 text-sm font-medium text-gray-300 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            >
              <Key className="w-4 h-4" />
              USE DEMO CREDENTIALS
              <ChevronDown className="w-4 h-4" />
            </button>

            {showDemoMenu && (
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 rounded-md shadow-xl bg-gray-800 border border-gray-700 py-1 z-50 animate-in fade-in zoom-in-95">
                <button
                  onClick={() => populateDemo('demo.admin')}
                  className="w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
                >
                  Admin
                </button>
                <button
                  onClick={() => populateDemo('demo.operator')}
                  className="w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
                >
                  Control Room Operator
                </button>
                <button
                  onClick={() => populateDemo('demo.maintenance')}
                  className="w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
                >
                  Maintenance Officer
                </button>
                <button
                  onClick={() => populateDemo('demo.viewer')}
                  className="w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
                >
                  Viewer
                </button>
              </div>
            )}
          </div>
          
          <div className="text-center space-y-1">
            <p className="text-xs text-blue-400/80">Demo access for presentation</p>
            <p className="text-[10px] text-gray-600">
              By logging in, you agree to the Municipal Data Access Policy. <br/>
              Unauthorized access is strictly prohibited.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
