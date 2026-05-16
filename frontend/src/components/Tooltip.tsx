// Tooltip — viewport-aware. Picks the side with the most room, flips
// when it would clip the screen edge, and renders into a portal so
// it's never trapped by overflow:hidden ancestors.

import {
  ReactNode,
  cloneElement,
  isValidElement,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';

type Side = 'top' | 'bottom' | 'left' | 'right';

type Props = {
  label: string;
  children: ReactNode;
  preferred?: Side;
  delay?: number;
};

type Pos = { side: Side; x: number; y: number };

const VIEWPORT_PAD = 8;

export default function Tooltip({ label, children, preferred = 'top', delay = 120 }: Props) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<Pos | null>(null);
  const showTimer = useRef<number | null>(null);
  const hostRef = useRef<HTMLElement | null>(null);
  const tipRef = useRef<HTMLDivElement | null>(null);

  // Measure & place
  const place = useCallback(() => {
    const host = hostRef.current;
    const tip = tipRef.current;
    if (!host || !tip) return;

    const hostRect = host.getBoundingClientRect();
    const tipRect = tip.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    // Space available on each side
    const space = {
      top:    hostRect.top,
      bottom: vh - hostRect.bottom,
      left:   hostRect.left,
      right:  vw - hostRect.right,
    };

    // Pick a side: preferred if it fits; otherwise the side with most room
    const fits: Record<Side, boolean> = {
      top:    space.top    >= tipRect.height + VIEWPORT_PAD,
      bottom: space.bottom >= tipRect.height + VIEWPORT_PAD,
      left:   space.left   >= tipRect.width  + VIEWPORT_PAD,
      right:  space.right  >= tipRect.width  + VIEWPORT_PAD,
    };
    let side: Side = preferred;
    if (!fits[side]) {
      const ranked = (Object.keys(space) as Side[]).sort((a, b) => space[b] - space[a]);
      side = ranked.find(s => fits[s]) ?? ranked[0];
    }

    let x = 0, y = 0;
    if (side === 'top') {
      x = hostRect.left + hostRect.width / 2;
      y = hostRect.top - 8;
    } else if (side === 'bottom') {
      x = hostRect.left + hostRect.width / 2;
      y = hostRect.bottom + 8;
    } else if (side === 'left') {
      x = hostRect.left - 8;
      y = hostRect.top + hostRect.height / 2;
    } else {
      x = hostRect.right + 8;
      y = hostRect.top + hostRect.height / 2;
    }

    // Clamp the centre so the tooltip never leaves the viewport
    const halfW = tipRect.width / 2;
    const halfH = tipRect.height / 2;
    if (side === 'top' || side === 'bottom') {
      x = Math.min(Math.max(x, halfW + VIEWPORT_PAD), vw - halfW - VIEWPORT_PAD);
    } else {
      y = Math.min(Math.max(y, halfH + VIEWPORT_PAD), vh - halfH - VIEWPORT_PAD);
    }

    setPos({ side, x, y });
  }, [preferred]);

  const show = useCallback(() => {
    if (showTimer.current) window.clearTimeout(showTimer.current);
    showTimer.current = window.setTimeout(() => {
      setOpen(true);
      // Wait for tip to mount then place
      requestAnimationFrame(place);
    }, delay);
  }, [delay, place]);

  const hide = useCallback(() => {
    if (showTimer.current) window.clearTimeout(showTimer.current);
    setOpen(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    const handler = () => place();
    window.addEventListener('resize', handler);
    window.addEventListener('scroll', handler, true);
    return () => {
      window.removeEventListener('resize', handler);
      window.removeEventListener('scroll', handler, true);
    };
  }, [open, place]);

  // Wrap children to attach refs + handlers
  const trigger = (() => {
    const handlers = {
      onMouseEnter: show,
      onMouseLeave: hide,
      onFocus: show,
      onBlur: hide,
      'aria-describedby': open ? id : undefined,
    };
    if (isValidElement(children)) {
      const el = children as React.ReactElement<{ ref?: React.Ref<HTMLElement> }>;
      const existingRef = (el as { ref?: React.Ref<HTMLElement> }).ref;
      const setRef = (node: HTMLElement | null) => {
        hostRef.current = node;
        if (typeof existingRef === 'function') existingRef(node);
        else if (existingRef && typeof existingRef === 'object')
          (existingRef as React.MutableRefObject<HTMLElement | null>).current = node;
      };
      return cloneElement(el, { ...(el.props || {}), ...handlers, ref: setRef } as any);
    }
    return (
      <span
        ref={el => { hostRef.current = el; }}
        {...handlers}
        className="inline-flex"
      >
        {children}
      </span>
    );
  })();

  return (
    <>
      {trigger}
      {open &&
        createPortal(
          <div
            id={id}
            ref={tipRef}
            role="tooltip"
            data-side={pos?.side ?? preferred}
            className={`tip ${pos ? 'is-visible' : ''}`}
            style={pos ? { left: pos.x, top: pos.y } : { visibility: 'hidden' }}
          >
            {label}
          </div>,
          document.body,
        )}
    </>
  );
}
