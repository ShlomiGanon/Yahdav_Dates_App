import { Navigate, useRoutes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { LoginPage } from './auth/LoginPage';
import { RequireAuth } from './auth/RequireAuth';
import { AppShell } from './layout/AppShell';
import { SECTION_REGISTRY } from './sections/_registry';
import type { RouteObject } from 'react-router-dom';

function AppRoutes() {
  return useRoutes([
    { path: '/login', element: <LoginPage /> },
    {
      element: <RequireAuth />,
      children: [
        {
          path: '/admin',
          element: <AppShell />,
          children: SECTION_REGISTRY.map((s) => s.route),
        },
      ],
    },
    { path: '/', element: <Navigate to="/admin/users" replace /> },
    { path: '*', element: <Navigate to="/admin/users" replace /> },
  ] satisfies RouteObject[]);
}

export function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
