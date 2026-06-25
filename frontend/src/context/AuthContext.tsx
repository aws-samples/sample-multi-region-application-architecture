// Authentication context — manages auth state across the React app.
// Tokens stored in localStorage; cleared explicitly on sign-out.

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { CognitoUser } from 'amazon-cognito-identity-js';
import { cognito, initCognito } from '../utils/cognito';
import type { SignUpParams } from '../utils/cognito';

export interface AuthUser {
  email: string;
  givenName: string;
  familyName: string;
  organization: string;
}

interface LoginResult {
  mfaRequired?: boolean;
  newPasswordRequired?: boolean;
  cognitoUser?: CognitoUser;
}

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<LoginResult>;
  completeNewPassword: (cognitoUser: CognitoUser, newPassword: string, attrs?: Record<string, string>) => Promise<void>;
  sendMfaCode: (cognitoUser: CognitoUser, code: string) => Promise<void>;
  signup: (params: SignUpParams) => Promise<void>;
  confirmEmail: (email: string, code: string) => Promise<void>;
  logout: () => void;
  forgotPassword: (email: string) => Promise<void>;
  resetPassword: (email: string, code: string, newPassword: string) => Promise<void>;
  getAccessToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, fetch runtime config then check for existing session
  useEffect(() => {
    initCognito().then(() => cognito.getSession()).then((session) => {
      if (session) {
        const payload = session.getIdToken().decodePayload();
        setUser({
          email: payload.email ?? '',
          givenName: payload.given_name ?? '',
          familyName: payload.family_name ?? '',
          organization: payload['custom:organization'] ?? '',
        });
      }
    }).finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<LoginResult> => {
    const result = await cognito.signIn(email, password);
    if (result.newPasswordRequired) {
      return { newPasswordRequired: true, cognitoUser: result.cognitoUser };
    }
    if (result.mfaRequired) {
      return { mfaRequired: true, cognitoUser: result.cognitoUser };
    }
    const payload = result.session.getIdToken().decodePayload();
    setUser({
      email: payload.email ?? '',
      givenName: payload.given_name ?? '',
      familyName: payload.family_name ?? '',
      organization: payload['custom:organization'] ?? '',
    });
    return {};
  }, []);

  const completeNewPassword = useCallback(async (cognitoUser: CognitoUser, newPassword: string, attrs?: Record<string, string>) => {
    const session = await cognito.completeNewPassword(cognitoUser, newPassword, attrs);
    const payload = session.getIdToken().decodePayload();
    setUser({
      email: payload.email ?? '',
      givenName: payload.given_name ?? '',
      familyName: payload.family_name ?? '',
      organization: payload['custom:organization'] ?? '',
    });
  }, []);

  const sendMfaCode = useCallback(async (cognitoUser: CognitoUser, code: string) => {
    const session = await cognito.sendMfaCode(cognitoUser, code);
    const payload = session.getIdToken().decodePayload();
    setUser({
      email: payload.email ?? '',
      givenName: payload.given_name ?? '',
      familyName: payload.family_name ?? '',
      organization: payload['custom:organization'] ?? '',
    });
  }, []);

  const signup = useCallback(async (params: SignUpParams) => {
    await cognito.signUp(params);
  }, []);

  const confirmEmail = useCallback(async (email: string, code: string) => {
    await cognito.confirmSignUp(email, code);
  }, []);

  const logout = useCallback(() => {
    cognito.signOut();
    setUser(null);
  }, []);

  const forgotPassword = useCallback(async (email: string) => {
    await cognito.forgotPassword(email);
  }, []);

  const resetPassword = useCallback(async (email: string, code: string, newPassword: string) => {
    await cognito.confirmForgotPassword(email, code, newPassword);
  }, []);

  const getAccessToken = useCallback(() => cognito.getAccessToken(), []);

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user,
      isLoading,
      login, completeNewPassword, sendMfaCode, signup, confirmEmail, logout,
      forgotPassword, resetPassword, getAccessToken,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
