'use client';

import * as React from 'react';
import { Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

interface FileUploadButtonProps {
  onFilesSelected: (files: File[]) => void;
  accept?: string;
  multiple?: boolean;
  maxSizeMB?: number;
}

export function FileUploadButton({
  onFilesSelected,
  accept = '.pdf,.doc,.docx,.jpg,.jpeg,.png',
  multiple = true,
  maxSizeMB = 10,
}: FileUploadButtonProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;

    const files = Array.from(fileList);
    const totalSize = files.reduce((sum, f) => sum + f.size, 0);

    if (totalSize > maxSizeMB * 1024 * 1024) {
      toast.error(`Total file size must not exceed ${maxSizeMB}MB`);
      if (inputRef.current) inputRef.current.value = '';
      return;
    }

    onFilesSelected(files);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleChange}
        className="hidden"
      />
      <Button
        type="button"
        variant="outline"
        onClick={() => inputRef.current?.click()}
        className="border-border text-foreground hover:bg-accent"
      >
        <Upload className="h-4 w-4 mr-2" />
        Choose Files
      </Button>
    </>
  );
}
