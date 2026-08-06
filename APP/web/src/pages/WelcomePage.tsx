import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { PAGE_ROUTES } from './routes';
import heroImage from '../assets/hero.png';
import { clientMessage } from '@shared/copy/client';

export function WelcomePage()
{
    const navigate = useNavigate();

    return (
        <div className="min-h-screen bg-background flex items-center justify-center px-4 py-10">
            <div className="w-full max-w-4xl grid gap-8 sm:grid-cols-2 items-center">
                <img
                    src={heroImage}
                    alt=""
                    className="hidden sm:block w-full h-auto rounded-card object-cover max-h-96"
                />

                <div className="bg-surface rounded-card p-8 shadow-lg text-center">
                    <h1 className="text-3xl font-bold text-secondary mb-2">יחדיו</h1>
                    <p className="text-secondary opacity-70 mb-8">
                        המקום להכיר אנשים חדשים ולבנות קשר אמיתי.
                    </p>

                    <div className="flex flex-col gap-3">
                        <Button label={clientMessage('login_label')} onPress={() => navigate(PAGE_ROUTES.login)} />
                        <Button
                            label={clientMessage('signup_entry_label')}
                            variant="secondary"
                            onPress={() => navigate(PAGE_ROUTES.signup)}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
