// Pills for status / severity / category.

import { CSSProperties, ReactNode } from 'react';

type Tone = 'primary' | 'success' | 'danger' | 'warning' | 'neutral' | 'soft';

export default function Pill({
  tone = 'soft',
  children,
  icon,
  title,
  style,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  icon?: ReactNode;
  title?: string;
  style?: CSSProperties;
  className?: string;
}) {
  return (
    <span className={`pill pill-${tone}${className ? ' ' + className : ''}`} title={title} style={style}>
      {icon}
      {children}
    </span>
  );
}
