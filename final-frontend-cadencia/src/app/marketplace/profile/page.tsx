'use client';

import * as React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { toast } from 'sonner';
import { Loader2, Factory } from 'lucide-react';

import { AppShell } from '@/components/layout/AppShell';
import { SellerRoleGuard } from '@/components/shared/SellerRoleGuard';
import { SectionHeader } from '@/components/shared/SectionHeader';
import { FormField } from '@/components/shared/FormField';
import { TagInput } from '@/components/shared/TagInput';
import { EmbeddingStatus } from '@/components/shared/EmbeddingStatus';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { api } from '@/lib/api';

// ─── Constants ────────────────────────────────────────────────────────────────
const INDUSTRIES = [
  'Steel Manufacturing', 'Steel Trading', 'Aluminium', 'Copper',
  'Plastics', 'Textiles', 'Custom',
];
const PRODUCT_SUGGESTIONS = [
  'HR Coil', 'Cold Rolled', 'Wire Rod', 'TMT Bars',
  'Billets', 'Sheets', 'Plates', 'Pipes',
];
const GEOGRAPHY_SUGGESTIONS = [
  'Maharashtra', 'Gujarat', 'Karnataka', 'Tamil Nadu',
  'Pan-India', 'North India',
];

// ─── Schema ───────────────────────────────────────────────────────────────────
const sellerProfileSchema = z.object({
  industry: z.string().min(1, 'Industry is required'),
  products: z.array(z.string()).min(1, 'Add at least one product'),
  geographies: z.array(z.string()).min(1, 'Add at least one geography'),
  min_order_value: z.number({ error: 'Enter a valid amount' }).min(1000, 'Minimum INR 1,000'),
  max_order_value: z.number({ error: 'Enter a valid amount' }),
  description: z.string().min(10, 'Description must be at least 10 characters'),
}).refine(d => d.max_order_value > d.min_order_value, {
  message: 'Max must exceed min order value',
  path: ['max_order_value'],
});

type ProfileFormValues = z.infer<typeof sellerProfileSchema>;

// ─── Profile data shape from API ──────────────────────────────────────────────
interface SellerProfile {
  industry: string;
  geographies: string[];
  products: string[];
  min_order_value: number;
  max_order_value: number;
  description: string;
  embedding_status: 'active' | 'queued' | 'failed' | 'outdated';
  last_embedded: string | null;
}

export default function SellerProfilePage() {
  const queryClient = useQueryClient();

  // ─── Fetch profile ──────────────────────────────────────────────────────────
  const { data: profile } = useQuery<SellerProfile>({
    queryKey: ['seller-profile'],
    queryFn: () => api.get('/v1/marketplace/capability-profile').then(r => r.data.data),
  });

  // ─── Form ───────────────────────────────────────────────────────────────────
  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(sellerProfileSchema),
    defaultValues: {
      industry: '',
      products: [],
      geographies: [],
      min_order_value: 0,
      max_order_value: 0,
      description: '',
    },
    mode: 'onTouched',
  });

  // Sync form when profile data loads
  React.useEffect(() => {
    if (profile) {
      form.reset({
        industry: profile.industry,
        products: profile.products,
        geographies: profile.geographies,
        min_order_value: profile.min_order_value,
        max_order_value: profile.max_order_value,
        description: profile.description,
      });
    }
  }, [profile]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Embedding status state ─────────────────────────────────────────────────
  const [embeddingStatus, setEmbeddingStatus] = React.useState<'active' | 'queued' | 'failed' | 'outdated'>('active');
  const [lastEmbedded, setLastEmbedded] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (profile) {
      setEmbeddingStatus(profile.embedding_status);
      setLastEmbedded(profile.last_embedded);
    }
  }, [profile]);

  // ─── Save mutation ──────────────────────────────────────────────────────────
  const saveMutation = useMutation({
    mutationFn: async (data: ProfileFormValues) => {
      await api.put('/v1/marketplace/capability-profile', data);
      await api.post('/v1/marketplace/capability-profile/embeddings');
    },
    onSuccess: () => {
      toast.success('Profile saved! Embeddings queued -- active in ~30 seconds.');
      setEmbeddingStatus('queued');
      // Refetch after delay to show active
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['seller-profile'] });
      }, 5000);
    },
    onError: () => {
      toast.error('Failed to save profile');
    },
  });

  // ─── Embedding refresh ──────────────────────────────────────────────────────
  const refreshMutation = useMutation({
    mutationFn: () => api.post('/v1/marketplace/capability-profile/embeddings'),
    onSuccess: () => {
      toast.success('Embeddings refresh queued');
      setEmbeddingStatus('queued');
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['seller-profile'] });
      }, 5000);
    },
    onError: () => {
      toast.error('Failed to refresh embeddings');
    },
  });

  const { errors, touchedFields } = form.formState;

  return (
    <AppShell>
      <SellerRoleGuard>
        <div className="p-6">

          {/* Section 1: Hero Header */}
          <div className="bg-gradient-to-r from-primary/5 to-secondary/5 border border-border rounded-lg p-8 mb-8 text-center">
            <div className="bg-muted border border-border rounded-lg p-3 inline-block mb-4">
              <Factory className="h-6 w-6 text-primary" />
            </div>
            <h1 className="text-2xl font-semibold text-foreground mb-2">
              Tell AI about your capabilities
            </h1>
            <p className="text-lg text-muted-foreground">
              so buyers can find you automatically
            </p>
            <p className="text-sm text-muted-foreground mt-4 max-w-2xl mx-auto">
              Complete your profile to appear in buyer RFQ matches. Higher detail = better AI matching.
            </p>
          </div>

          <form onSubmit={form.handleSubmit((data) => saveMutation.mutate(data))}>

            {/* Section 2: Profile Fields */}
            <div className="bg-card border border-border rounded-lg p-6 mb-8">
              <SectionHeader title="Profile Fields" description="Structured data for AI matching algorithms" />

              <div className="space-y-6">
                {/* Industry */}
                <FormField
                  label="Industry"
                  required
                  error={touchedFields.industry ? errors.industry?.message : undefined}
                  hint="Your primary industry vertical"
                >
                  <Controller
                    control={form.control}
                    name="industry"
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select industry" />
                        </SelectTrigger>
                        <SelectContent position="popper" className="bg-popover border-border">
                          {INDUSTRIES.map(ind => (
                            <SelectItem key={ind} value={ind}>{ind}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </FormField>

                {/* Products */}
                <Controller
                  control={form.control}
                  name="products"
                  render={({ field }) => (
                    <TagInput
                      label="Products"
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="Type product and press Enter..."
                      error={errors.products?.message}
                      allowedValues={PRODUCT_SUGGESTIONS}
                    />
                  )}
                />

                {/* Geographies */}
                <Controller
                  control={form.control}
                  name="geographies"
                  render={({ field }) => (
                    <TagInput
                      label="Geographies"
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="Type region and press Enter..."
                      error={errors.geographies?.message}
                      allowedValues={GEOGRAPHY_SUGGESTIONS}
                    />
                  )}
                />

                {/* Order Values */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  <FormField
                    label="Min Order Value"
                    required
                    error={errors.min_order_value?.message}
                    hint="Minimum order you accept"
                  >
                    <div className="relative">
                      <span className="absolute left-3 top-2.5 text-sm font-medium text-muted-foreground">INR</span>
                      <Input
                        type="number"
                        className="pl-12"
                        {...form.register('min_order_value', { valueAsNumber: true })}
                      />
                    </div>
                  </FormField>

                  <FormField
                    label="Max Order Value"
                    required
                    error={errors.max_order_value?.message}
                    hint="Maximum order capacity"
                  >
                    <div className="relative">
                      <span className="absolute left-3 top-2.5 text-sm font-medium text-muted-foreground">INR</span>
                      <Input
                        type="number"
                        className="pl-12"
                        {...form.register('max_order_value', { valueAsNumber: true })}
                      />
                    </div>
                  </FormField>
                </div>
              </div>
            </div>

            {/* Section 3: Free-text Description */}
            <div className="bg-card border border-border rounded-lg p-6 mb-8">
              <SectionHeader
                title="Free-text Description"
                description="Used for AI semantic matching beyond structured fields"
              />
              <FormField
                label="Capability Description"
                required
                error={touchedFields.description ? errors.description?.message : undefined}
                hint='Example: "ISO 9001 certified HR Coil manufacturer with 2MT/day capacity. Pan-India delivery within 30 days. LC at sight preferred. Bulk discounts available."'
              >
                <textarea
                  rows={8}
                  {...form.register('description')}
                  placeholder="Tell us about your capabilities, certifications, delivery network, payment terms, etc. This helps AI understand your full offering beyond structured fields."
                  className="flex w-full rounded-md border border-border bg-input px-3 py-2 text-sm text-foreground ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-vertical"
                />
              </FormField>
            </div>

            {/* Section 4: Embedding Status + Save */}
            <div className="bg-card border border-border rounded-lg p-6">
              <SectionHeader title="AI Matching Status" />

              <div className="mb-6">
                <EmbeddingStatus
                  status={embeddingStatus}
                  lastUpdated={lastEmbedded ?? undefined}
                  onRefresh={() => refreshMutation.mutate()}
                  isRefreshing={refreshMutation.isPending}
                />
              </div>

              <div className="flex justify-end">
                <Button
                  type="submit"
                  disabled={saveMutation.isPending}
                  className="w-full sm:w-auto bg-primary text-primary-foreground hover:bg-primary/90 px-8"
                >
                  {saveMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save Profile'
                  )}
                </Button>
              </div>
            </div>
          </form>
        </div>
      </SellerRoleGuard>
    </AppShell>
  );
}
