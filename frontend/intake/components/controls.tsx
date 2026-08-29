'use client';

/** Shared button primitives used across every step screen. Kept tiny and
 *  dependency-free — no component library, matches the rest of the app. */

export function BigButton({
  onClick,
  children,
  variant = 'primary',
  disabled,
  highlighted,
}: {
  onClick: () => void;
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost';
  disabled?: boolean;
  /** The voice matcher picked this option — shown briefly before it
   *  auto-submits, so the patient sees what was understood rather than
   *  the screen simply jumping. */
  highlighted?: boolean;
}) {
  const base = 'w-full text-left px-6 py-5 rounded-2xl text-lg font-medium transition-colors disabled:opacity-40';
  const styles: Record<string, React.CSSProperties> = {
    primary: { background: 'var(--mp-red)', color: 'white' },
    secondary: { background: 'var(--bg-raised)', color: 'var(--text)', border: '1px solid var(--line)' },
    ghost: { background: 'transparent', color: 'var(--text-dim)' },
  };
  const style = highlighted
    ? { ...styles[variant], outline: '3px solid var(--mp-red)', outlineOffset: 2 }
    : styles[variant];
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={base} style={style}>
      {children}
    </button>
  );
}

export function TextField({
  value,
  onChange,
  placeholder,
  autoFocus,
  onSubmit,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
  onSubmit?: () => void;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      autoFocus={autoFocus}
      rows={3}
      className="w-full px-5 py-4 rounded-2xl text-lg resize-none outline-none"
      style={{ background: 'var(--bg-raised)', color: 'var(--text)', border: '1px solid var(--line)' }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && !e.shiftKey && onSubmit) {
          e.preventDefault();
          onSubmit();
        }
      }}
    />
  );
}

export function ContinueBar({
  onContinue,
  disabled,
  label,
}: {
  onContinue: () => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onContinue}
      disabled={disabled}
      className="w-full mt-4 px-6 py-4 rounded-2xl text-lg font-semibold transition-opacity disabled:opacity-30"
      style={{ background: 'var(--mp-ink)', color: 'white' }}
    >
      {label}
    </button>
  );
}
