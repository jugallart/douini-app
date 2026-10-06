import { createBrowserRouter, Navigate } from "react-router";
import { tokenStore } from "./lib/tokenStore";
import { Login } from "./pages/auth/Login";
import { Signup } from "./pages/auth/Signup";
import { VerifyEmail } from "./pages/auth/VerifyEmail";
import { ForgotPassword } from "./pages/auth/ForgotPassword";
import { ResetPassword } from "./pages/auth/ResetPassword";
import { Wizard } from "./pages/Wizard";
import { Dashboard } from "./pages/Dashboard";
import { Plan } from "./pages/Plan";
import { Profile } from "./pages/Profile";
import { Pantheon } from "./pages/Pantheon";
import { Settings } from "./pages/Settings";
import { Releases } from "./pages/Releases";
import { NotFound } from "./pages/NotFound";

function Protected({ children }: { children: React.ReactNode }) {
  if (!tokenStore.getAccessToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  { path: "/signup", element: <Signup /> },
  { path: "/verify-email", element: <VerifyEmail /> },
  { path: "/forgot-password", element: <ForgotPassword /> },
  { path: "/reset-password", element: <ResetPassword /> },
  { path: "/wizard", element: <Protected><Wizard /></Protected> },
  { path: "/", element: <Protected><Dashboard /></Protected> },
  { path: "/plan", element: <Protected><Plan /></Protected> },
  { path: "/profile", element: <Protected><Profile /></Protected> },
  { path: "/pantheon", element: <Protected><Pantheon /></Protected> },
  { path: "/settings", element: <Protected><Settings /></Protected> },
  { path: "/releases", element: <Protected><Releases /></Protected> },
  { path: "*", element: <NotFound /> },
]);
