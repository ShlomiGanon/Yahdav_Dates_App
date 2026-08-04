import { useRef } from 'react';

interface Props
{
    onFile:   (file: File) => void;
    label?:   string;
    disabled?: boolean;
}

export function PhotoUpload({ onFile, label = 'העלה תמונה', disabled = false }: Props)
{
    const inputRef = useRef<HTMLInputElement>(null);

    function handleChange(e: React.ChangeEvent<HTMLInputElement>): void
    {
        const file = e.target.files?.[0];

        if (file)
        {
            onFile(file);
            e.target.value = '';
        }
    }

    return (
        <>
            <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={handleChange}
            />
            <button
                type="button"
                disabled={disabled}
                className="px-4 py-2 bg-primary text-white rounded-card
                           disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => inputRef.current?.click()}
            >
                {label}
            </button>
        </>
    );
}
