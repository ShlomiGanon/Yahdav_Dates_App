import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';

export function LoginPage()
{
    const { login }                         = useAuth();
    const navigate                          = useNavigate();
    const [identifier, setIdentifier]       = useState('');
    const [password,   setPassword]         = useState('');
    const [error,      setError]            = useState('');
    const [loading,    setLoading]          = useState(false);

    async function handleSubmit(e: React.FormEvent): Promise<void>
    {
        e.preventDefault();
        setError('');
        setLoading(true);

        try
        {
            await login(identifier, password);
            navigate('/discover', { replace: true });
        }
        catch
        {
            setError('שם משתמש או סיסמה שגויים');
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

                <form onSubmit={handleSubmit} className="flex flex-col gap-4">

                    <div className="flex flex-col gap-1">
                        <label className="text-sm text-secondary">
                            אימייל או שם משתמש
                        </label>
                        <input
                            type="text"
                            value={identifier}
                            onChange={(e) => setIdentifier(e.target.value)}
                            required
                            className="border border-gray-300 rounded-lg px-4 py-3
                                       text-base text-right focus:outline-none
                                       focus:border-primary"
                        />
                    </div>

                    <div className="flex flex-col gap-1">
                        <label className="text-sm text-secondary">
                            סיסמה
                        </label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            className="border border-gray-300 rounded-lg px-4 py-3
                                       text-base text-right focus:outline-none
                                       focus:border-primary"
                        />
                    </div>

                    {error && (
                        <p className="text-danger text-sm text-center">{error}</p>
                    )}

                    <Button
                        label="התחברות"
                        onPress={() => {}}
                        loading={loading}
                        disabled={!identifier || !password}
                    />

                </form>
            </div>
        </div>
    );
}
