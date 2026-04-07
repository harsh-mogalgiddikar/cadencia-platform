'use client';

import * as React from 'react';
import { X, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TagInputProps {
  value: string[];
  onChange: (value: string[]) => void;
  placeholder: string;
  label: string;
  error?: string;
  allowedValues?: string[];
}

export function TagInput({ value, onChange, placeholder, label, error, allowedValues }: TagInputProps) {
  const [input, setInput] = React.useState('');
  const [showSuggestions, setShowSuggestions] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const suggestions = React.useMemo(() => {
    if (!allowedValues || !input.trim()) return [];
    const lower = input.toLowerCase();
    return allowedValues.filter(
      v => v.toLowerCase().includes(lower) && !value.includes(v)
    ).slice(0, 6);
  }, [allowedValues, input, value]);

  const addTag = (tag: string) => {
    const trimmed = tag.trim().replace(/,$/, '');
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInput('');
    setShowSuggestions(false);
  };

  const removeTag = (tag: string) => {
    onChange(value.filter(v => v !== tag));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      if (input.trim()) addTag(input);
    }
    if (e.key === 'Backspace' && !input && value.length > 0) {
      removeTag(value[value.length - 1]);
    }
  };

  return (
    <div className="space-y-1.5 w-full">
      <label className="text-sm font-medium text-foreground">{label}</label>
      <div
        className={cn(
          'flex flex-wrap items-center gap-1 p-2 border border-border bg-input rounded-md min-h-10 cursor-text',
          error && 'border-destructive ring-1 ring-destructive'
        )}
        onClick={() => inputRef.current?.focus()}
      >
        {value.map(tag => (
          <span
            key={tag}
            className="inline-flex items-center bg-secondary text-secondary-foreground rounded-md px-2 py-0.5 text-xs"
          >
            {tag}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); removeTag(tag); }}
              className="ml-1 hover:text-destructive transition-colors"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        <div className="relative flex-1 min-w-[100px]">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => { setInput(e.target.value); setShowSuggestions(true); }}
            onKeyDown={handleKeyDown}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => {
              // Delay to allow suggestion click
              setTimeout(() => setShowSuggestions(false), 150);
              if (input.trim()) addTag(input);
            }}
            placeholder={value.length === 0 ? placeholder : ''}
            className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute left-0 top-full mt-1 w-full bg-popover border border-border rounded-md shadow-md z-20 py-1">
              {suggestions.map(s => (
                <button
                  key={s}
                  type="button"
                  onMouseDown={(e) => { e.preventDefault(); addTag(s); }}
                  className="w-full text-left px-3 py-1.5 text-sm text-foreground hover:bg-accent transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      {error && (
        <div className="flex items-center gap-1 text-xs text-destructive mt-1">
          <AlertCircle className="h-3 w-3 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
