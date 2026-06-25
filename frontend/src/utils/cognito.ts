// Cognito authentication service — wraps amazon-cognito-identity-js SDK.
// Config is fetched at runtime from /api/config so the same build works in any account.

import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserAttribute,
  CognitoUserSession,
} from 'amazon-cognito-identity-js';

// Runtime config — fetched once from backend, cached in memory
let _config: { cognitoUserPoolId: string; cognitoClientId: string; region: string } | null = null;
let _userPool: CognitoUserPool | null = null;

async function getConfig() {
  if (!_config) {
    const resp = await fetch('/api/config');
    _config = await resp.json();
  }
  return _config!;
}

async function getUserPool(): Promise<CognitoUserPool> {
  if (!_userPool) {
    const config = await getConfig();
    _userPool = new CognitoUserPool({
      UserPoolId: config.cognitoUserPoolId,
      ClientId: config.cognitoClientId,
    });
  }
  return _userPool;
}

// Synchronous access for cases where pool is already initialized
function getUserPoolSync(): CognitoUserPool {
  if (!_userPool) throw new Error('Cognito not initialized — call initCognito() first');
  return _userPool;
}

// Call this once at app startup (e.g., in main.tsx or AuthContext)
export async function initCognito(): Promise<void> {
  await getUserPool();
}

function clearCognitoStorage(): void {
  Object.keys(localStorage)
    .filter(k => k.startsWith('CognitoIdentityServiceProvider.'))
    .forEach(k => localStorage.removeItem(k));
}

export interface SignUpParams {
  email: string;
  password: string;
  givenName: string;
  familyName: string;
  organization: string;
}

export interface SignInResult {
  session: CognitoUserSession;
  mfaRequired?: boolean;
  newPasswordRequired?: boolean;
  cognitoUser?: CognitoUser;
}

function attr(name: string, value: string): CognitoUserAttribute {
  return new CognitoUserAttribute({ Name: name, Value: value });
}

export const cognito = {
  signUp({ email, password, givenName, familyName, organization }: SignUpParams): Promise<void> {
    const pool = getUserPoolSync();
    const attributes = [
      attr('email', email),
      attr('given_name', givenName),
      attr('family_name', familyName),
      attr('custom:organization', organization),
    ];
    return new Promise((resolve, reject) => {
      pool.signUp(email, password, attributes, [], (err) => {
        if (err) return reject(err);
        resolve();
      });
    });
  },

  confirmSignUp(email: string, code: string): Promise<void> {
    const pool = getUserPoolSync();
    const user = new CognitoUser({ Username: email, Pool: pool });
    return new Promise((resolve, reject) => {
      user.confirmRegistration(code, true, (err) => {
        if (err) return reject(err);
        resolve();
      });
    });
  },

  signIn(email: string, password: string): Promise<SignInResult> {
    const pool = getUserPoolSync();
    const user = new CognitoUser({ Username: email, Pool: pool });
    const authDetails = new AuthenticationDetails({ Username: email, Password: password });
    return new Promise((resolve, reject) => {
      user.authenticateUser(authDetails, {
        onSuccess: (session) => resolve({ session }),
        onFailure: (err) => reject(err),
        totpRequired: () => resolve({ session: null as unknown as CognitoUserSession, mfaRequired: true, cognitoUser: user }),
        newPasswordRequired: () => resolve({ session: null as unknown as CognitoUserSession, newPasswordRequired: true, cognitoUser: user }),
      });
    });
  },

  completeNewPassword(cognitoUser: CognitoUser, newPassword: string, attrs?: Record<string, string>): Promise<CognitoUserSession> {
    return new Promise((resolve, reject) => {
      cognitoUser.completeNewPasswordChallenge(newPassword, attrs || {}, {
        onSuccess: (session) => resolve(session),
        onFailure: (err) => reject(err),
      });
    });
  },

  sendMfaCode(cognitoUser: CognitoUser, code: string): Promise<CognitoUserSession> {
    return new Promise((resolve, reject) => {
      cognitoUser.sendMFACode(code, {
        onSuccess: (session) => resolve(session),
        onFailure: (err) => reject(err),
      }, 'SOFTWARE_TOKEN_MFA');
    });
  },

  signOut(): void {
    const pool = getUserPoolSync();
    const user = pool.getCurrentUser();
    if (user) user.signOut();
    clearCognitoStorage();
  },

  forgotPassword(email: string): Promise<void> {
    const pool = getUserPoolSync();
    const user = new CognitoUser({ Username: email, Pool: pool });
    return new Promise((resolve, reject) => {
      user.forgotPassword({
        onSuccess: () => resolve(),
        onFailure: (err) => reject(err),
      });
    });
  },

  confirmForgotPassword(email: string, code: string, newPassword: string): Promise<void> {
    const pool = getUserPoolSync();
    const user = new CognitoUser({ Username: email, Pool: pool });
    return new Promise((resolve, reject) => {
      user.confirmPassword(code, newPassword, {
        onSuccess: () => resolve(),
        onFailure: (err) => reject(err),
      });
    });
  },

  setupTotp(): Promise<string> {
    const pool = getUserPoolSync();
    const user = pool.getCurrentUser();
    if (!user) return Promise.reject(new Error('No user'));
    return new Promise((resolve, reject) => {
      user.getSession((err: Error | null) => {
        if (err) return reject(err);
        user.associateSoftwareToken({
          associateSecretCode: (secret) => resolve(secret),
          onFailure: (err) => reject(err),
        });
      });
    });
  },

  verifyTotp(code: string): Promise<void> {
    const pool = getUserPoolSync();
    const user = pool.getCurrentUser();
    if (!user) return Promise.reject(new Error('No user'));
    return new Promise((resolve, reject) => {
      user.verifySoftwareToken(code, 'TOTP', {
        onSuccess: () => {
          user.setUserMfaPreference(null, { PreferredMfa: true, Enabled: true }, (err) => {
            if (err) return reject(err);
            resolve();
          });
        },
        onFailure: (err) => reject(err),
      });
    });
  },

  getSession(): Promise<CognitoUserSession | null> {
    const pool = getUserPoolSync();
    const user = pool.getCurrentUser();
    if (!user) return Promise.resolve(null);
    return new Promise((resolve) => {
      user.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session || !session.isValid()) return resolve(null);
        resolve(session);
      });
    });
  },

  async getAccessToken(): Promise<string | null> {
    const session = await this.getSession();
    return session?.getAccessToken().getJwtToken() ?? null;
  },
};
