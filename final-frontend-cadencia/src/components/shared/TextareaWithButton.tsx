'use client';

import * as React from 'react';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface TextareaWithButtonProps {
  placeholder: string;
  buttonText: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  isLoading?: boolean;
  disabled?: boolean;
  rows?: number;
}

export function TextareaWithButton({
  placeholder,
  buttonText,
  value,
  onChange,
  onSubmit,
  isLoading = false,
  disabled = false,
  rows = 6,
}: TextareaWithButtonProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (value.trim().length > 0 && !isLoading && !disabled) {
        onSubmit();
      }
    }
  };

  return (
    <div className="space-y-3">
      <textarea
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isLoading || disabled}
        className="flex w-full rounded-md border border-border bg-input px-3 py-2 text-sm text-foreground ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-vertical"
      />
      <div className="flex justify-between items-center">
        <p className="text-xs text-muted-foreground">Press Ctrl+Enter to submit</p>
        <Button
          onClick={onSubmit}
          disabled={value.trim().length === 0 || isLoading || disabled}
          className="bg-primary text-primary-foreground hover:bg-primary/90"
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Submitting...
            </>
          ) : (
            buttonText
          )}
        </Button>
      </div>
    </div>
  );
}
