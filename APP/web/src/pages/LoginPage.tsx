import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';

export function LoginPage()
{
    const { login }                   = useAuth();
    const navigate                    = useNavigate();
    const [identifier, setIdentifier] = useState('');
    const [password,   setPassword]   = useState('');
    const [error,      setError]      = useState('');
    const [loading,    setLoading]    = useState(false);

    async function handleSubmit(e: React.FormEvent): Promise<void>
    {
        e.preventDefault();
        setError('');

        // Client-side validation before ever hitting the server.
        if (!identifier.trim() || !password)
        {
            setError('יש למלא את כל השדות');
            return;
        }

        setLoading(true);
        try
        {
            const result = await login(identifier.trim(), password);

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
                    יחדיו
                </h1>

                <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>

                    <div className="flex flex-col gap-1">
                        <label htmlFor="login-identifier" className="text-sm text-secondary">
                            אימייל או שם משתמש
                        </label>
                        <input
                            id="login-identifier"
                            type="text"
                            value={identifier}
                            onChange={(e) => setIdentifier(e.target.value)}
                            className="border border-gray-300 rounded-lg px-4 py-3
                                       text-base text-right focus:outline-none
                                       focus:border-primary"
                        />
                    </div>

                    <div className="flex flex-col gap-1">
                        <label htmlFor="login-password" className="text-sm text-secondary">
                            סיסמה
                        </label>
                        <input
                            id="login-password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
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
                        label="התחברות"
                        loading={loading}
                    />

                    <Link to="/signup" className="text-sm text-center text-secondary underline">
                        אין לך חשבון? הרשמה
                    </Link>

                </form>
            </div>
        </div>
    );
}
