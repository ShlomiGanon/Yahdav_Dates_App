interface Props
{
    message:      string;
    confirmLabel: string;
    cancelLabel?: string;
    variant?:     'danger' | 'primary';
    onConfirm:    () => void;
    onCancel:     () => void;
}

// Inline replacement for window.confirm() — a small styled container that
// lives in the page's own layout (not a modal overlay, not a blocking OS
// dialog), using the same bg-surface/rounded-card/palette tokens as the
// rest of the app. Beyond matching the design system, a native confirm()
// blocks all further script execution on the tab until a human dismisses
// it — this can't do that, since it's just conditionally-rendered state.
export function ConfirmBanner({
    message,
    confirmLabel,
    cancelLabel = 'ביטול',
    variant     = 'danger',
    onConfirm,
    onCancel,
}: Props)
{
    const confirmClass = variant === 'danger' ? 'bg-danger' : 'bg-primary';

    return (
        <div
            role="alertdialog"
            aria-live="assertive"
            className="bg-surface border border-gray-200 rounded-card p-4 mb-4 flex flex-col gap-3"
        >
            <p className="text-secondary text-sm">{message}</p>
            <div className="flex gap-3 justify-end">
                <button
                    type="button"
                    onClick={onCancel}
                    className="px-4 py-2 text-sm text-secondary underline"
                >
                    {cancelLabel}
                </button>
                <button
                    type="button"
                    onClick={onConfirm}
                    className={`px-4 py-2 rounded-card text-sm font-semibold text-white ${confirmClass}`}
                >
                    {confirmLabel}
                </button>
            </div>
        </div>
    );
}
