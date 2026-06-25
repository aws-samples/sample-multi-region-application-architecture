import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { AppProvider } from './context/AppContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Header } from './components/Header';
import { Home } from './pages/Home';
import { AirportList } from './pages/AirportList';
import { AddAirport } from './pages/AddAirport';
import { Tech } from './pages/Tech';
import { Crew } from './pages/Crew';
import { Login } from './pages/auth/Login';
import { SignUp } from './pages/auth/SignUp';
import { VerifyEmail } from './pages/auth/VerifyEmail';
import { ForgotPassword } from './pages/auth/ForgotPassword';
import { ResetPassword } from './pages/auth/ResetPassword';
import { MfaSetup } from './pages/auth/MfaSetup';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public auth routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<SignUp />} />
          <Route path="/verify" element={<VerifyEmail />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />

          {/* Protected app routes */}
          <Route path="/*" element={
            <ProtectedRoute>
              <AppProvider>
                <div className="min-h-screen bg-surface text-slate-200">
                  <Header />
                  <main className="max-w-7xl mx-auto px-6 py-8">
                    <Routes>
                      <Route path="/" element={<Home />} />
                      <Route path="/airports" element={<AirportList />} />
                      <Route path="/add" element={<AddAirport />} />
                      <Route path="/tech" element={<Tech />} />
                      <Route path="/crew" element={<Crew />} />
                      <Route path="/mfa-setup" element={<MfaSetup />} />
                    </Routes>
                  </main>
                </div>
              </AppProvider>
            </ProtectedRoute>
          } />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
