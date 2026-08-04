interface Props
{
    onPress:   () => void;
    label:     string;
    variant?:  'primary' | 'secondary';
    loading?:  boolean;
    disabled?: boolean;
}

export function Button(
{
    onPress,
    label,
    variant  = 'primary',
    loading  = false,
    disabled = false,
}: Props)
{
    const base = 'w-full py-4 rounded-card text-lg font-semibold transition-opacity';

    const colours = variant === 'primary'
        ? 'bg-primary text-white'
        : 'border border-secondary text-secondary bg-transparent';

    return (
        <button
            type="button"
            disabled={disabled || loading}
            onClick={onPress}
            className={`${base} ${colours} disabled:opacity-50 disabled:cursor-not-allowed`}
        >
            {loading ? '...' : label}
        </button>
    );
}
