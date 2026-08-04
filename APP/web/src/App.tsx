import { Routes, Route, Navigate } from 'react-router-dom';
import { RequireAuth }      from './auth/RequireAuth';
import { RedirectIfAuthed } from './auth/RedirectIfAuthed';
import { LoginPage }        from './pages/LoginPage';
import { SignupPage }       from './pages/SignupPage';
import { DiscoverPage }     from './pages/DiscoverPage';
import { ProfilePage }      from './pages/ProfilePage';
import { PeerProfilePage }  from './pages/PeerProfilePage';
import { ChatHistoryPage }  from './pages/ChatHistoryPage';
import { ChatPage }         from './pages/ChatPage';

export default function App()
{
    return (
        <Routes>
            <Route element={<RedirectIfAuthed />}>
                <Route path="/login"  element={<LoginPage />} />
                <Route path="/signup" element={<SignupPage />} />
            </Route>

            <Route element={<RequireAuth />}>
                <Route path="/discover"            element={<DiscoverPage />} />
                <Route path="/profile"             element={<ProfilePage />} />
                <Route path="/peer/:peer_id"       element={<PeerProfilePage />} />
                <Route path="/chat"                element={<ChatHistoryPage />} />
                <Route path="/chat/:peer_id"       element={<ChatPage />} />
                <Route index                       element={<Navigate to="/discover" replace />} />
            </Route>

            <Route path="*" element={<Navigate to="/discover" replace />} />
        </Routes>
    );
}
