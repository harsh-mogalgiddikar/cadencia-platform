'use client';

import * as React from 'react';
import { Loader2 } from 'lucide-react';
import { FormField } from '@/components/shared/FormField';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';

interface HumanOverridePanelProps {
  onSubmit: (offer: { price: number; terms: Record<string, string> }) => void;
  isSubmitting: boolean;
}

export function HumanOverridePanel({ onSubmit, isSubmitting }: HumanOverridePanelProps) {
  const [price, setPrice] = React.useState('');
  const [termsText, setTermsText] = React.useState('{\n  "delivery": "FOB Mumbai",\n  "payment": "LC at sight"\n}');

  const handleSubmit = () => {
    const priceNum = parseInt(price);
    if (!priceNum || priceNum <= 0) {
      toast.error('Enter a valid price');
      return;
    }

    let terms: Record<string, string>;
    try {
      terms = JSON.parse(termsText);
    } catch {
      toast.error('Invalid JSON in terms field');
      return;
    }

    onSubmit({ price: priceNum, terms });
  };

  return (
    <div className="space-y-4">
      <FormField label="Override Price" required hint="Your manual price offer in INR">
        <div className="relative">
          <span className="absolute left-3 top-2.5 text-sm font-medium text-muted-foreground">INR</span>
          <Input
            type="number"
            className="pl-12"
            placeholder="41000"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
        </div>
      </FormField>

      <FormField label="Terms (JSON)" hint="Key-value pairs for delivery, payment, warranty, etc.">
        <textarea
          rows={5}
          value={termsText}
          onChange={(e) => setTermsText(e.target.value)}
          className="flex w-full rounded-md border border-border bg-input px-3 py-2 text-sm text-foreground font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-vertical"
        />
      </FormField>

      <div className="flex justify-end">
        <Button
          onClick={handleSubmit}
          disabled={isSubmitting || !price}
          className="bg-primary text-primary-foreground hover:bg-primary/90"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Submitting...
            </>
          ) : (
            'Submit Override'
          )}
        </Button>
      </div>
    </div>
  );
}
