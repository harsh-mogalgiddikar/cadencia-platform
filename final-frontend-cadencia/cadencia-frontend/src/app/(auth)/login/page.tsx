'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Building2, AlertCircle, Loader2 } from 'lucide-react';

import { useAuth } from '@/hooks/useAuth';
import { api, setAccessToken } from '@/lib/api';
import { ROUTES } from '@/lib/constants';
import { FormField } from '@/components/shared/FormField';
import { PasswordInput } from '@/components/shared/PasswordInput';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const loginSchema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 bg-red-950 border border-destructive/40 rounded-lg p-3 text-sm text-destructive mb-4">
      <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
      <span>{message}</span>
    </div>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const [globalError, setGlobalError] = React.useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, touchedFields, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    mode: 'onTouched',
  });

  React.useEffect(() => {
    if (!isLoading && user) {
      router.replace(ROUTES.DASHBOARD);
    }
  }, [user, isLoading, router]);

  const onSubmit = async (data: LoginFormValues) => {
    setGlobalError(null);
    try {
      const response = await api.post('/v1/auth/login', data);
      setAccessToken(response.data.data.access_token);
      router.push(ROUTES.DASHBOARD);
    } catch (err: any) {
      if (err.response?.status === 401) {
        setGlobalError('Invalid email or password. Please try again.');
      } else {
        setGlobalError('Unable to connect. Please try again.');
      }
    }
  };

  if (isLoading || user) {
    return null; // Return null while checking auth to prevent flash of login content
  }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
      <div className="bg-card border border-border rounded-lg p-8 w-full max-w-sm">
        <div className="flex flex-col items-center mb-6">
          <div className="bg-muted border border-border rounded-lg p-3 mb-4">
            <Building2 className="h-6 w-6 text-primary" />
          </div>
          <h1 className="text-xl font-semibold text-foreground mb-1">Cadencia</h1>
          <p className="text-sm text-muted-foreground">AI-powered B2B trade platform</p>
        </div>

        <div className="border-t border-border w-full mb-6" />

        <h2 className="text-base font-semibold text-foreground mb-6">Sign in to your account</h2>

        {globalError && <ErrorBanner message={globalError} />}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            label="Email address"
            required
            error={touchedFields.email ? errors.email?.message : undefined}
          >
            <Input
              type="email"
  className={touchedFields.email && errors.email ? 'border-destructive ring-destructive' : ''}
              {...register('email')}
            />
          </FormField>

          <FormField
            label="Password"
            required
            error={touchedFields.password ? errors.password?.message : undefined}
          >
            <PasswordInput
              error={touchedFields.password && !!errors.password}
              {...register('password')}
            />
          </FormField>

          <Button type="submit" disabled={isSubmitting} className="w-full bg-primary text-primary-foreground hover:bg-primary/90 mt-2">
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Signing in...
              </>
            ) : (
              'Sign In'
            )}
          </Button>
        </form>

        <div className="border-t border-border w-full my-6" />

        <p className="text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{' '}
          <Link href={ROUTES.REGISTER} className="text-primary hover:underline">
            Create one here
          </Link>
        </p>
      </div>

      {process.env.NODE_ENV === 'development' && (
        <div className="mt-8 text-xs text-muted-foreground bg-muted p-2 rounded border border-border">
          Test: admin@tatasteel.com / password123
        </div>
      )}
    </div>
  );
}
