'use client';

import * as React from 'react';
import { Copy, AlertTriangle } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

interface ApiKeyModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  apiKey: {
    id: string;
    label: string;
    key: string;
    created_at: string;
  } | null;
}

export function ApiKeyModal({ open, onOpenChange, apiKey }: ApiKeyModalProps) {
  if (!apiKey) return null;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(apiKey.key);
    toast.success('Copied!');
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border text-foreground max-w-md">
        <DialogHeader>
          <DialogTitle className="text-foreground">API Key Created</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <p className="text-sm text-muted-foreground mb-1">Label</p>
            <p className="text-sm font-medium text-foreground">{apiKey.label}</p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground mb-1">Key</p>
            <div className="font-mono text-sm bg-muted rounded-md p-3 w-full text-center text-foreground break-all select-all">
              {apiKey.key}
            </div>
          </div>

          <div className="bg-destructive/10 border border-destructive/20 rounded-md p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <p className="text-xs text-muted-foreground">
                This key is shown only once -- copy and store securely.
              </p>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleCopy}
              className="flex-1 border-border text-foreground hover:bg-accent"
            >
              <Copy className="h-4 w-4 mr-2" />
              Copy to Clipboard
            </Button>
            <Button
              onClick={() => onOpenChange(false)}
              className="flex-1 bg-primary text-primary-foreground hover:bg-primary/90"
            >
              I Have Copied
            </Button>
          </div>

          <div className="space-y-1 text-xs text-muted-foreground">
            <p>Never share your API key with others</p>
            <p>Revoke and regenerate if compromised</p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
