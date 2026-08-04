import { Routes, Route, Navigate } from 'react-router-dom';
import { RequireAuth }      from './auth/RequireAuth';
import { RedirectIfAuthed } from './auth/RedirectIfAuthed';
import { WEB_DESTINATIONS } from './auth/destinations';
import { PAGE_ROUTES }      from './pages/routes';
import { WelcomePage }          from './pages/WelcomePage';
import { LoginPage }            from './pages/LoginPage';
import { SignupPage }           from './pages/SignupPage';
import { MenuPage }             from './pages/MenuPage';
import { ProfilePage }          from './pages/ProfilePage';
import { AdditionalPhotosPage } from './pages/AdditionalPhotosPage';
import { DiscoverPage }         from './pages/DiscoverPage';
import { PeerProfilePage }      from './pages/PeerProfilePage';
import { PeerPhotosPage }       from './pages/PeerPhotosPage';
import { ChatHistoryPage }      from './pages/ChatHistoryPage';
import { ChatPage }             from './pages/ChatPage';

export default function App()
{
    return (
        <Routes>
            <Route element={<RedirectIfAuthed />}>
                <Route path={PAGE_ROUTES.welcome} element={<WelcomePage />} />
                <Route path={PAGE_ROUTES.login}   element={<LoginPage />} />
                <Route path={PAGE_ROUTES.signup}  element={<SignupPage />} />
            </Route>

            <Route element={<RequireAuth />}>
                <Route path={PAGE_ROUTES.menu}             element={<MenuPage />} />
                <Route path={PAGE_ROUTES.profile}          element={<ProfilePage />} />
                <Route path={PAGE_ROUTES.additionalPhotos} element={<AdditionalPhotosPage />} />
                <Route path={PAGE_ROUTES.discover}         element={<DiscoverPage />} />
                <Route path={PAGE_ROUTES.peerProfile}      element={<PeerProfilePage />} />
                <Route path={PAGE_ROUTES.peerPhotos}       element={<PeerPhotosPage />} />
                <Route path={PAGE_ROUTES.chatHistory}      element={<ChatHistoryPage />} />
                <Route path={PAGE_ROUTES.chat}             element={<ChatPage />} />
                <Route index                               element={<Navigate to={WEB_DESTINATIONS.home} replace />} />
            </Route>

            <Route path="*" element={<Navigate to={WEB_DESTINATIONS.home} replace />} />
        </Routes>
    );
}
