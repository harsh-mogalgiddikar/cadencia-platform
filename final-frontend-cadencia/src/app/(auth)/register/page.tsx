'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import * as z from 'zod';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { AlertCircle, Loader2, X, Pencil } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '@/hooks/useAuth';
import { formatCurrency, cn } from '@/lib/utils';

// We import the real constants to use ROUTES, but alias it since some formatters are in utils
import { ROUTES as AppRoutes } from '@/lib/constants';

import { FormField } from '@/components/shared/FormField';
import { PasswordInput } from '@/components/shared/PasswordInput';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 bg-red-950 border border-destructive/40 rounded-lg p-3 text-sm text-destructive mb-4">
      <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
      <span>{message}</span>
    </div>
  );
}

const step1Schema = z.object({
  legal_name: z.string().min(2, 'Legal name must be at least 2 characters'),
  pan: z.string().regex(/^[A-Z]{5}[0-9]{4}[A-Z]{1}$/, 'Enter a valid PAN (e.g. ABCDE1234F)'),
  gstin: z.string().regex(
    /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/,
    'Enter a valid 15-character GSTIN'
  ),
  trade_role: z.enum(['BUYER', 'SELLER', 'BOTH'], { error: 'Select a trade role' }),
  industry_vertical: z.string().min(2, 'Industry is required'),
  geography: z.string().min(2, 'Geography is required'),
  commodities: z.array(z.string()).min(1, 'Add at least one commodity'),
  min_order_value: z.number({ error: 'Enter a valid amount' }).min(1000, 'Minimum order must be at least ₹1,000'),
  max_order_value: z.number({ error: 'Enter a valid amount' }),
}).refine(d => d.max_order_value > d.min_order_value, {
  message: 'Max order value must be greater than min order value',
  path: ['max_order_value'],
});

const step2Schema = z.object({
  full_name: z.string().min(2, 'Full name must be at least 2 characters'),
  email: z.string().email('Enter a valid email address'),
  password: z.string()
    .min(8, 'Password must be at least 8 characters')
    .regex(/[A-Z]/, 'Must contain at least one uppercase letter')
    .regex(/[0-9]/, 'Must contain at least one number'),
  confirm_password: z.string(),
}).refine(d => d.password === d.confirm_password, {
  message: 'Passwords do not match',
  path: ['confirm_password'],
});

type Step1Values = z.infer<typeof step1Schema>;
type Step2Values = z.infer<typeof step2Schema>;

interface RegistrationState {
  step: 1 | 2 | 3;
  enterprise: Step1Values | null;
  user: Step2Values | null;
}

export default function RegisterPage() {
  const router = useRouter();
  const auth = useAuth();
  const { user, isLoading } = auth;
  
  const [state, setState] = React.useState<RegistrationState>({
    step: 1,
    enterprise: null,
    user: null,
  });

  const [globalError, setGlobalError] = React.useState<string | null>(null);
  const [isSubmittingForm, setIsSubmittingForm] = React.useState(false);

  React.useEffect(() => {
    if (!isLoading && user) {
      router.replace(AppRoutes.DASHBOARD);
    }
  }, [user, isLoading, router]);

  const goToStep = (step: 1 | 2 | 3) => {
    setGlobalError(null);
    setState(s => ({ ...s, step }));
  };

  const handleStep1Submit = (data: Step1Values) => {
    setState(s => ({ ...s, enterprise: data, step: 2 }));
  };

  const handleStep2Submit = (data: Step2Values) => {
    setState(s => ({ ...s, user: data, step: 3 }));
  };

  const submitRegistration = async () => {
    setGlobalError(null);
    setIsSubmittingForm(true);
    
    if (!state.enterprise || !state.user) {
      setIsSubmittingForm(false);
      return;
    }

    const payload = {
      enterprise: { ...state.enterprise },
      user: {
        email: state.user.email,
        password: state.user.password,
        full_name: state.user.full_name,
        role: 'ADMIN',
      }
    };

    try {
      await auth.register(payload);
      toast.success('Account created successfully. Welcome to Cadencia.');
    } catch (err: any) {
      if (err.response?.status === 409) {
        setGlobalError('An account with this email or PAN already exists.');
      } else if (err.response?.status === 422) {
        setGlobalError('Validation failed on server. Please check your data.');
      } else {
        setGlobalError('Registration failed. Please try again.');
      }
      setIsSubmittingForm(false);
    }
  };

  if (isLoading || user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center py-10 px-4">
      <div className="bg-card border border-border rounded-lg w-full max-w-lg shadow-sm flex flex-col">
        <div className="p-6 md:p-8">
          <StepIndicator currentStep={state.step} />
          {globalError && <ErrorBanner message={globalError} />}
          
          {state.step === 1 && (
            <Step1Form 
              initialData={state.enterprise} 
              onSubmit={handleStep1Submit} 
            />
          )}

          {state.step === 2 && (
            <Step2Form 
              initialData={state.user} 
              onSubmit={handleStep2Submit} 
              onBack={() => goToStep(1)} 
            />
          )}

          {state.step === 3 && state.enterprise && state.user && (
            <Step3Review 
              enterprise={state.enterprise} 
              user={state.user} 
              onEditEnterprise={() => goToStep(1)}
              onEditUser={() => goToStep(2)}
              onSubmit={submitRegistration}
              isSubmitting={isSubmittingForm}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function StepIndicator({ currentStep }: { currentStep: number }) {
  const steps = [
    { num: 1, label: 'Enterprise Info' },
    { num: 2, label: 'Admin User' },
    { num: 3, label: 'Review & Submit' },
  ];

  return (
    <div className="flex items-center justify-between mb-8 relative">
      {/* Connecting lines between steps */}
      {[0, 1].map((i) => (
        <div
          key={i}
          className={cn(
            'absolute top-[15px] h-[2px] z-0',
            i === 0 ? 'left-[calc(16.67%)] right-[calc(50%+16px)]' : 'left-[calc(50%+16px)] right-[calc(16.67%)]',
            currentStep > i + 1 ? 'bg-primary' : 'bg-border'
          )}
        />
      ))}
      {steps.map((step) => {
        const isCompleted = currentStep > step.num;
        const isCurrent = currentStep === step.num;
        const isUpcoming = currentStep < step.num;

        return (
          <div key={step.num} className="relative z-10 flex flex-col items-center gap-2">
            <div
              className={cn(
                'flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium transition-colors',
                isCompleted && 'bg-primary text-primary-foreground',
                isCurrent && 'bg-primary text-primary-foreground ring-2 ring-primary ring-offset-2 ring-offset-background',
                isUpcoming && 'bg-muted text-muted-foreground border border-border'
              )}
            >
              {step.num}
            </div>
            <span
              className={cn(
                'text-xs whitespace-nowrap',
                isCurrent ? 'text-primary font-medium' : 'text-muted-foreground'
              )}
            >
              {step.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 1 Form
// ─────────────────────────────────────────────────────────────────────────────

function Step1Form({ initialData, onSubmit }: { initialData: Step1Values | null, onSubmit: (data: Step1Values) => void }) {
  const { register, control, handleSubmit, formState: { errors, touchedFields }, setValue, watch } = useForm<Step1Values>({
    resolver: zodResolver(step1Schema),
    defaultValues: initialData || {
      commodities: [],
      trade_role: undefined,
    },
    mode: 'onTouched',
  });

  const commodities = watch('commodities') || [];
  const [commodityInput, setCommodityInput] = React.useState('');

  const handleAddCommodity = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      const val = commodityInput.trim().replace(/,$/, '');
      if (val && !commodities.includes(val)) {
        setValue('commodities', [...commodities, val], { shouldValidate: true, shouldDirty: true });
        setCommodityInput('');
      }
    }
  };

  const removeCommodity = (item: string) => {
    setValue('commodities', commodities.filter(c => c !== item), { shouldValidate: true, shouldDirty: true });
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 animate-in fade-in slide-in-from-bottom-2">
      <FormField label="Legal Name" required error={touchedFields.legal_name ? errors.legal_name?.message : undefined}>
        <Input {...register('legal_name')} />
      </FormField>

      <div className="grid grid-cols-2 gap-4">
        <FormField label="PAN" required error={touchedFields.pan ? errors.pan?.message : undefined}>
          <Input {...register('pan')} className="uppercase" />
        </FormField>
        <FormField label="GSTIN" required error={touchedFields.gstin ? errors.gstin?.message : undefined}>
          <Input {...register('gstin')} className="uppercase" />
        </FormField>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <FormField label="Trade Role" required error={errors.trade_role?.message}>
          <Controller
            control={control}
            name="trade_role"
            render={({ field }) => (
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <SelectTrigger>
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent position="popper" className="bg-popover border-border">
                  <SelectItem value="BUYER">Buyer</SelectItem>
                  <SelectItem value="SELLER">Seller</SelectItem>
                  <SelectItem value="BOTH">Buyer & Seller</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </FormField>

        <FormField label="Industry Vertical" required error={touchedFields.industry_vertical ? errors.industry_vertical?.message : undefined}>
          <Input {...register('industry_vertical')} />
        </FormField>
      </div>

      <FormField label="Geography" hint="Primary state or region" required error={touchedFields.geography ? errors.geography?.message : undefined}>
        <Input {...register('geography')} />
      </FormField>

      <FormField label="Commodities" required error={errors.commodities?.message}>
        <div className={cn("flex flex-wrap items-center gap-2 p-2 border border-border bg-input rounded-md min-h-10", errors.commodities && "border-destructive ring-1 ring-destructive")}>
          {commodities.map(c => (
            <span key={c} className="flex items-center gap-1 bg-secondary text-secondary-foreground rounded-md pl-2 pr-1 py-0.5 text-xs">
              {c}
              <button type="button" onClick={() => removeCommodity(c)} className="hover:text-destructive transition-colors shrink-0 p-0.5">
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          <input
            type="text"
            className="flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground min-w-[120px]"
            placeholder="Type and press Enter..."
            value={commodityInput}
            onChange={e => setCommodityInput(e.target.value)}
            onKeyDown={handleAddCommodity}
            onBlur={(e) => {
              if (commodityInput.trim()) {
                const val = commodityInput.trim();
                if (!commodities.includes(val)) {
                  setValue('commodities', [...commodities, val], { shouldValidate: true, shouldDirty: true });
                }
                setCommodityInput('');
              }
            }}
          />
        </div>
      </FormField>

      <div className="grid grid-cols-2 gap-4">
        <FormField label="Min Order Value" required error={errors.min_order_value?.message}>
          <div className="relative">
            <span className="absolute left-3 top-2.5 text-sm font-medium text-muted-foreground">INR</span>
            <Input 
              type="number" 
              className="pl-12" 
              {...register('min_order_value', { valueAsNumber: true })} 
            />
          </div>
        </FormField>
        <FormField label="Max Order Value" required error={errors.max_order_value?.message}>
          <div className="relative">
            <span className="absolute left-3 top-2.5 text-sm font-medium text-muted-foreground">INR</span>
            <Input 
              type="number" 
              className="pl-12" 
              {...register('max_order_value', { valueAsNumber: true })} 
            />
          </div>
        </FormField>
      </div>

      <div className="pt-2">
        <Button type="submit" className="w-full bg-primary text-primary-foreground hover:bg-primary/90">
          Next
        </Button>
      </div>
    </form>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 2 Form
// ─────────────────────────────────────────────────────────────────────────────

function getPasswordStrengthOptions(pwd: string) {
  let criteria = 0;
  if (!pwd) return { criteria: 0, label: '', color: 'bg-muted', text: '' };
  
  if (pwd.length >= 8) criteria++;
  if (/[A-Z]/.test(pwd)) criteria++;
  if (/[0-9]/.test(pwd)) criteria++;
  if (/[^a-zA-Z0-9]/.test(pwd)) criteria++;

  const configs: Record<number, { label: string, color: string, text: string }> = {
    0: { label: '', color: 'bg-muted', text: '' },
    1: { label: 'Weak', color: 'bg-destructive', text: 'text-destructive' },
    2: { label: 'Fair', color: 'bg-amber-500', text: 'text-amber-500' },
    3: { label: 'Good', color: 'bg-amber-400', text: 'text-amber-400' },
    4: { label: 'Strong', color: 'bg-green-500', text: 'text-green-500' },
  };

  return { criteria, ...configs[criteria] };
}

function Step2Form({ initialData, onSubmit, onBack }: { initialData: Step2Values | null, onSubmit: (data: Step2Values) => void, onBack: () => void }) {
  const { register, handleSubmit, watch, formState: { errors, touchedFields } } = useForm<Step2Values>({
    resolver: zodResolver(step2Schema),
    defaultValues: initialData || {},
    mode: 'onTouched',
  });

  const pwd = watch('password');
  const strength = getPasswordStrengthOptions(pwd);

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 animate-in fade-in slide-in-from-bottom-2">
      <FormField label="Full Name" required error={touchedFields.full_name ? errors.full_name?.message : undefined}>
        <Input {...register('full_name')} />
      </FormField>

      <FormField label="Email address" required error={touchedFields.email ? errors.email?.message : undefined}>
        <Input type="email" {...register('email')} />
      </FormField>

      <FormField label="Password" required error={touchedFields.password ? errors.password?.message : undefined}>
        <PasswordInput error={touchedFields.password && !!errors.password} {...register('password')} />
        <div className="mt-2 flex items-center justify-between">
          <div className="flex gap-1 flex-1 max-w-[200px]">
            {[1, 2, 3, 4].map((i) => (
              <div 
                key={i} 
                className={cn("h-1 w-full rounded-full transition-colors", strength.criteria >= i ? strength.color : "bg-muted")} 
              />
            ))}
          </div>
          <span className={cn("text-xs w-10 text-right font-medium", strength.text)}>
            {strength.label}
          </span>
        </div>
      </FormField>

      <FormField label="Confirm Password" required error={touchedFields.confirm_password ? errors.confirm_password?.message : undefined}>
        <PasswordInput error={touchedFields.confirm_password && !!errors.confirm_password} {...register('confirm_password')} />
      </FormField>

      <div className="flex gap-3 pt-2">
        <Button type="button" variant="ghost" onClick={onBack} className="w-1/3 hover:bg-accent text-foreground">
          Back
        </Button>
        <Button type="submit" className="flex-1 bg-primary text-primary-foreground hover:bg-primary/90">
          Next
        </Button>
      </div>
    </form>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 3 Review
// ─────────────────────────────────────────────────────────────────────────────

function Step3Review({ 
  enterprise, user, onEditEnterprise, onEditUser, onSubmit, isSubmitting 
}: { 
  enterprise: Step1Values, user: Step2Values, onEditEnterprise: () => void, onEditUser: () => void, onSubmit: () => void, isSubmitting: boolean 
}) {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2">
      
      {/* Enterprise Card */}
      <div className="bg-card border border-border rounded-lg p-5 relative">
        <button onClick={onEditEnterprise} className="absolute top-4 right-4 p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors" title="Edit Enterprise">
          <Pencil className="h-4 w-4" />
        </button>
        <h3 className="text-sm font-semibold text-foreground mb-4">Enterprise Details</h3>
        
        <div className="grid grid-cols-2 gap-y-4 gap-x-2">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Legal Name</p>
            <p className="text-sm text-foreground">{enterprise.legal_name}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Trade Role</p>
            <p className="text-sm text-foreground">{enterprise.trade_role}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">PAN</p>
            <p className="text-sm text-foreground uppercase">{enterprise.pan}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">GSTIN</p>
            <p className="text-sm text-foreground uppercase">{enterprise.gstin}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Industry</p>
            <p className="text-sm text-foreground">{enterprise.industry_vertical}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Geography</p>
            <p className="text-sm text-foreground">{enterprise.geography}</p>
          </div>
          <div className="col-span-2 flex gap-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Min Order</p>
              <p className="text-sm text-foreground">{formatCurrency(enterprise.min_order_value)}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Max Order</p>
              <p className="text-sm text-foreground">{formatCurrency(enterprise.max_order_value)}</p>
            </div>
          </div>
          <div className="col-span-2">
            <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Commodities</p>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {enterprise.commodities.map(c => (
                <span key={c} className="bg-secondary text-secondary-foreground text-xs px-2 py-0.5 rounded-md">
                  {c}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* User Card */}
      <div className="bg-card border border-border rounded-lg p-5 relative">
        <button onClick={onEditUser} className="absolute top-4 right-4 p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors" title="Edit Admin User">
          <Pencil className="h-4 w-4" />
        </button>
        <h3 className="text-sm font-semibold text-foreground mb-4">Admin User</h3>
        
        <div className="space-y-3">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Full Name</p>
              <p className="text-sm text-foreground">{user.full_name}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1 text-right">Role</p>
              <StatusBadge status="ADMIN" size="sm" /> 
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Email Address</p>
            <p className="text-sm text-foreground">{user.email}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Password</p>
            <p className="text-sm text-foreground">••••••••</p>
          </div>
        </div>
      </div>

      <div className="pt-2">
        <Button onClick={onSubmit} disabled={isSubmitting} className="w-full bg-primary text-primary-foreground hover:bg-primary/90">
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Creating account...
            </>
          ) : (
            'Create Account'
          )}
        </Button>
        <p className="text-xs text-muted-foreground text-center mt-3">
          By creating an account you agree to Cadencia&apos;s terms of service.
        </p>
      </div>

    </div>
  );
}
