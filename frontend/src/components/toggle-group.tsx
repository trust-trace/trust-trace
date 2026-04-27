'use client';

import React from 'react';

export interface ToggleOption<T extends string = string> {
  value: T;
  label: string;
}

interface ToggleGroupProps<T extends string = string> {
  options: ToggleOption<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: 'sm' | 'md' | 'lg';
  /** Optional ARIA role attributes */
  role?: string;
  ariaLabel?: string;
}

export function ToggleGroup<T extends string = string>({
  options,
  value,
  onChange,
  size = 'md',
  role,
  ariaLabel,
}: ToggleGroupProps<T>) {
  return (
    <div
      className={`tt-toggle-group tt-toggle-group--${size}`}
      {...(role ? { role } : {})}
      {...(ariaLabel ? { 'aria-label': ariaLabel } : {})}
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={`tt-toggle-item${opt.value === value ? ' is-active' : ''}`}
          onClick={() => onChange(opt.value)}
          aria-pressed={opt.value === value}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
