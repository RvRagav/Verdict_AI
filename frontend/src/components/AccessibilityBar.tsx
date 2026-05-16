// Accessibility controls — A / A+ / A++ text size + contrast slider.
// Uses native `title` for the segmented buttons (zero overlap risk).

import { useEffect, useState } from 'react';
import { Eye } from 'lucide-react';

type Size = 'base' | 'l' | 'xl';

const SIZE_KEY = 'verdictai.text-size';
const CONTRAST_KEY = 'verdictai.contrast';

function applySize(size: Size) {
  const root = document.documentElement;
  root.classList.remove('text-l', 'text-xl');
  if (size === 'l')  root.classList.add('text-l');
  if (size === 'xl') root.classList.add('text-xl');
}

function applyContrast(value: number) {
  const root = document.documentElement;
  root.style.setProperty('--contrast-amp', String(value / 100));
  root.classList.toggle('contrast-high', value >= 50);
}

export default function AccessibilityBar() {
  const [size, setSize] = useState<Size>(
    () => (localStorage.getItem(SIZE_KEY) as Size) || 'base',
  );
  const [contrast, setContrast] = useState<number>(
    () => Number(localStorage.getItem(CONTRAST_KEY) ?? '0'),
  );

  useEffect(() => {
    applySize(size);
    localStorage.setItem(SIZE_KEY, size);
  }, [size]);

  useEffect(() => {
    applyContrast(contrast);
    localStorage.setItem(CONTRAST_KEY, String(contrast));
  }, [contrast]);

  return (
    <div className="flex items-center gap-3">
      <div className="segmented" role="group" aria-label="Text size">
        <button
          type="button"
          className={`segmented-item ${size === 'base' ? 'is-active' : ''}`}
          onClick={() => setSize('base')}
          aria-pressed={size === 'base'}
          title="Default text size"
        >
          A
        </button>
        <button
          type="button"
          className={`segmented-item ${size === 'l' ? 'is-active' : ''}`}
          onClick={() => setSize('l')}
          aria-pressed={size === 'l'}
          title="Larger text"
        >
          A+
        </button>
        <button
          type="button"
          className={`segmented-item ${size === 'xl' ? 'is-active' : ''}`}
          onClick={() => setSize('xl')}
          aria-pressed={size === 'xl'}
          title="Largest text"
        >
          A++
        </button>
      </div>

      <label
        className="flex items-center gap-2 px-2 py-1 rounded-md border border-line-strong bg-bg cursor-pointer"
        title={`Contrast: ${contrast}%`}
      >
        <Eye size={13} className="text-ink-muted" aria-hidden />
        <input
          className="range"
          type="range"
          min={0}
          max={100}
          step={5}
          value={contrast}
          onChange={e => setContrast(Number(e.target.value))}
          aria-label="Contrast level"
        />
      </label>
    </div>
  );
}
