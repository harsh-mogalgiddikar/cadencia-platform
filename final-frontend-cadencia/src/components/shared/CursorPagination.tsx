import * as React from 'react';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface CursorPaginationProps<T> {
  data: T[];
  hasMore: boolean;
  isLoading: boolean;
  loadMore: () => void;
}

export function CursorPagination<T>({ data, hasMore, isLoading, loadMore }: CursorPaginationProps<T>) {
  if (data.length === 0 && !isLoading) {
    return (
      <div className="py-8 text-center text-muted-foreground text-sm">
        No records found.
      </div>
    );
  }

  return (
    <div className="py-4 flex flex-col items-center border-t border-border bg-muted/10">
      <p className="text-xs text-muted-foreground mb-4">
        Showing {data.length} records
      </p>
      {hasMore && (
        <Button 
          variant="outline" 
          size="sm" 
          onClick={loadMore} 
          disabled={isLoading}
        >
          {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          Load More
        </Button>
      )}
      {!hasMore && data.length > 0 && (
        <p className="text-xs text-muted-foreground italic">
          End of log
        </p>
      )}
    </div>
  );
}
