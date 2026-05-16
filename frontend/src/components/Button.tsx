// Colour-coded buttons. The COLOUR is the affordance.
// No tooltip layer here — the visible text label IS the explanation.
// Icon-only buttons elsewhere should be wrapped in <Tooltip> manually.
//
//   primary  — proceed / save / start (blue pencil)
//   success  — accept / approve (green pencil)
//   danger   — reject / fail / delete (red pencil)
//   warning  — needs review / caution (amber pencil)
//   ghost    — neutral / cancel (white outline)

import { ButtonHTMLAttributes, ReactNode, forwardRef } from 'react';

type Variant = 'primary' | 'success' | 'danger' | 'warning' | 'ghost' | 'link';
type Size = 'sm' | 'md' | 'lg';

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
};

const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = 'primary', size = 'md', icon, className = '', children, ...rest },
  ref,
) {
  const cls = [
    'btn',
    `btn-${variant}`,
    size === 'sm' ? 'btn-sm' : size === 'lg' ? 'btn-lg' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <button ref={ref} className={cls} {...rest}>
      {icon && <span className="inline-flex">{icon}</span>}
      {children}
    </button>
  );
});

export default Button;
