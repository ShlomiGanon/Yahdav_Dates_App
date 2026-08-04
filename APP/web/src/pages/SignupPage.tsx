import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';

// Derive a username from the email local-part (strip domain, sanitize) —
// mirrors mobile/src/screens/signup/SignupScreen.tsx's deriveUsername.
function deriveUsername(email: string): string
{
    return (email.split('@')[0] ?? '')
        .replace(/[^a-zA-Z0-9_]/g, '')
        .toLowerCase()
        .slice(0, 30);
}

export function SignupPage()
{
    const { signup }                 = useAuth();
    const navigate                   = useNavigate();
    const [email,    setEmail]       = useState('');
    const [password, setPassword]    = useState('');
    const [confirm,  setConfirm]     = useState('');
    const [error,    setError]       = useState('');
    const [loading,  setLoading]     = useState(false);

    async function handleSubmit(e: React.FormEvent): Promise<void>
    {
        e.preventDefault();
        setError('');

        if (!email.trim() || !password || !confirm)
        {
            setError('יש למלא את כל השדות');
            return;
        }
        if (password !== confirm)
        {
            setError('הסיסמאות אינן תואמות');
            return;
        }
        if (password.length < 8)
        {
            setError('הסיסמה חייבת להכיל לפחות 8 תווים');
            return;
        }

        setLoading(true);
        try
        {
            const username = deriveUsername(email.trim());
            const result = await signup(email.trim(), username, password);

            if (!result.success)
            {
                setError(result.message);
                return;
            }

            navigate('/discover', { replace: true });
        }
        catch
        {
            setError('שגיאת רשת, נסה שוב');
        }
        finally
        {
            setLoading(false);
        }
    }

    return (
        <div className="min-h-screen bg-background flex items-center justify-center px-4">
            <div className="w-full max-w-sm bg-surface rounded-card p-8 shadow-lg">

                <h1 className="text-3xl font-bold text-center text-secondary mb-8">
                    הרשמה
                </h1>

                <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>

                    <div className="flex flex-col gap-1">
                        <label htmlFor="signup-email" className="text-sm text-secondary">
                            אימייל
                        </label>
                        <input
                            id="signup-email"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="border border-gray-300 rounded-lg px-4 py-3
                                       text-base text-right focus:outline-none
                                       focus:border-primary"
                        />
                    </div>

                    <div className="flex flex-col gap-1">
                        <label htmlFor="signup-password" className="text-sm text-secondary">
                            סיסמה
                        </label>
                        <input
                            id="signup-password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="לפחות 8 תווים"
                            className="border border-gray-300 rounded-lg px-4 py-3
                                       text-base text-right focus:outline-none
                                       focus:border-primary"
                        />
                    </div>

                    <div className="flex flex-col gap-1">
                        <label htmlFor="signup-confirm" className="text-sm text-secondary">
                            אימות סיסמה
                        </label>
                        <input
                            id="signup-confirm"
                            type="password"
                            value={confirm}
                            onChange={(e) => setConfirm(e.target.value)}
                            className="border border-gray-300 rounded-lg px-4 py-3
                                       text-base text-right focus:outline-none
                                       focus:border-primary"
                        />
                    </div>

                    {error && (
                        <p className="text-danger text-sm text-center" role="alert">{error}</p>
                    )}

                    <Button
                        type="submit"
                        label="הירשם"
                        loading={loading}
                    />

                    <Link to="/login" className="text-sm text-center text-secondary underline">
                        יש לך חשבון? התחברות
                    </Link>

                </form>
            </div>
        </div>
    );
}
