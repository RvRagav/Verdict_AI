// Light card primitive.

import { HTMLAttributes, ReactNode } from 'react';

export function Card({
  children,
  hover,
  className = '',
  ...rest
}: HTMLAttributes<HTMLDivElement> & { hover?: boolean }) {
  return (
    <div className={`card ${hover ? 'card-hover' : ''} ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="px-5 py-4 flex items-start justify-between border-b border-line">
      <div>
        <div className="text-md font-semibold text-ink">{title}</div>
        {subtitle && <div className="text-sm text-ink-soft mt-1">{subtitle}</div>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function CardBody({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`p-5 ${className}`}>{children}</div>;
}
