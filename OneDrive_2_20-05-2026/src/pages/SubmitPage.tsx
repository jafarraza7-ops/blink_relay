import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowLeft, ArrowRight, Bug, Check, File, Sparkles, Upload, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useCreateRequest } from '@/hooks/useRequests'
import { useToast } from '@/components/ui/use-toast'
import { filesApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import { formatBytes } from '@/lib/utils'
import { PODS, POD_DESCRIPTIONS, REGIONS, REGION_LABELS, ALLOWED_FILE_TYPES, MAX_FILE_SIZE_BYTES } from '@/lib/constants'
import type { RequestType, Priority, Region } from '@/lib/types'

// ── Schema ────────────────────────────────────────────────────────────────────

const submitSchema = z.object({
  request_type: z.enum(['Feature', 'Defect'] as const),
  priority: z.enum(['Critical', 'High', 'Medium', 'Low'] as const),
  pod: z.enum(['Charger', 'Driver', 'Revenue', 'Data', 'DevOps', 'Denali'] as const),
  region: z.array(z.enum(['NA', 'UK', 'EU'] as const)).min(1, 'Select at least one region'),
  title: z.string().min(5, 'Title must be at least 5 characters').max(200),
  business_problem: z.string().min(20, 'Please provide at least 20 characters'),
  expected_outcome: z.string().optional(),
  steps_to_reproduce: z.string().optional(),
  affected_area: z.string().min(3, 'Please describe the affected area'),
  additional_context: z.string().optional(),
})

type SubmitForm = z.infer<typeof submitSchema>

// ── Step indicator ─────────────────────────────────────────────────────────────

const STEPS = ['Type & Priority', 'Details', 'Attachments']

function StepIndicator({ current }: { current: number }) {
  return (
    <nav aria-label="Form steps" className="flex items-center justify-center gap-2 mb-8">
      {STEPS.map((label, i) => (
        <div key={label} className="flex items-center gap-2">
          <div
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold border-2 transition-colors',
              i < current
                ? 'border-primary bg-primary text-primary-foreground'
                : i === current
                ? 'border-primary bg-background text-primary'
                : 'border-muted bg-background text-muted-foreground'
            )}
            aria-current={i === current ? 'step' : undefined}
          >
            {i < current ? <Check className="h-4 w-4" /> : i + 1}
          </div>
          <span className={cn('text-sm hidden sm:block', i === current ? 'font-medium' : 'text-muted-foreground')}>
            {label}
          </span>
          {i < STEPS.length - 1 && <div className="w-8 h-px bg-border mx-1" aria-hidden />}
        </div>
      ))}
    </nav>
  )
}

// ── Step 1: Type toggle + Priority radio cards + Pod ──────────────────────────

const PRIORITY_CONFIG: Array<{ value: Priority; label: string; desc: string; color: string }> = [
  { value: 'Critical', label: 'Critical', desc: 'Blocking production', color: 'border-red-400 text-red-700' },
  { value: 'High', label: 'High', desc: 'Major impact', color: 'border-orange-400 text-orange-700' },
  { value: 'Medium', label: 'Medium', desc: 'Moderate impact', color: 'border-yellow-400 text-yellow-700' },
  { value: 'Low', label: 'Low', desc: 'Minor / nice to have', color: 'border-slate-300 text-slate-600' },
]

function Step1({ form }: { form: UseFormReturn<SubmitForm> }) {
  const type = form.watch('request_type')
  const priority = form.watch('priority')
  const pod = form.watch('pod')
  const regions = (form.watch('region') ?? []) as Region[]

  const toggleRegion = (r: Region) => {
    const current = regions
    const next = current.includes(r) ? current.filter((x) => x !== r) : [...current, r]
    form.setValue('region', next, { shouldValidate: true })
  }

  return (
    <div className="space-y-6">
      {/* Request type toggle */}
      <div>
        <h2 className="text-lg font-semibold mb-1">What kind of request?</h2>
        <p className="text-sm text-muted-foreground mb-4">Choose whether you&apos;re reporting a defect or requesting a new feature.</p>
        <div className="grid grid-cols-2 gap-3">
          {([
            ['Feature', Sparkles, 'A new capability or enhancement'] as const,
            ['Defect', Bug, 'Something broken that needs fixing'] as const,
          ]).map(([t, Icon, desc]) => (
            <button
              key={t}
              type="button"
              onClick={() => form.setValue('request_type', t as RequestType)}
              className={cn(
                'flex flex-col items-center gap-2 rounded-lg border-2 p-4 text-center transition-all hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                type === t ? 'border-primary bg-primary/5' : 'border-border'
              )}
              aria-pressed={type === t}
            >
              <Icon className={cn('h-8 w-8', type === t ? 'text-primary' : 'text-muted-foreground')} />
              <span className="font-semibold text-sm">{t}</span>
              <span className="text-xs text-muted-foreground">{desc}</span>
            </button>
          ))}
        </div>
        {form.formState.errors.request_type && (
          <p className="text-sm text-destructive mt-2" role="alert">{form.formState.errors.request_type.message}</p>
        )}
      </div>

      {/* Severity radio cards */}
      <div>
        <h2 className="text-lg font-semibold mb-1">Priority</h2>
        <p className="text-sm text-muted-foreground mb-4">How urgently does this need to be addressed?</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {PRIORITY_CONFIG.map(({ value, label, desc, color }) => (
            <button
              key={value}
              type="button"
              onClick={() => form.setValue('priority', value)}
              className={cn(
                'flex flex-col items-start rounded-lg border-2 px-3 py-3 text-left transition-all hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                priority === value ? cn('border-2 bg-primary/5', color) : 'border-border'
              )}
              aria-pressed={priority === value}
            >
              <span className={cn('font-semibold text-sm', priority === value ? color.split(' ')[1] : '')}>{label}</span>
              <span className="text-xs text-muted-foreground leading-tight mt-0.5">{desc}</span>
            </button>
          ))}
        </div>
        {form.formState.errors.priority && (
          <p className="text-sm text-destructive mt-2" role="alert">{form.formState.errors.priority.message}</p>
        )}
      </div>

      {/* Pod selection */}
      <div>
        <h2 className="text-lg font-semibold mb-1">Engineering POD</h2>
        <p className="text-sm text-muted-foreground mb-4">Select the team best suited to handle this request.</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {PODS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => form.setValue('pod', p)}
              className={cn(
                'flex flex-col items-start rounded-lg border-2 px-4 py-3 text-left transition-all hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                pod === p ? 'border-primary bg-primary/5' : 'border-border'
              )}
              aria-pressed={pod === p}
            >
              <span className="font-semibold text-sm">{p}</span>
              <span className="text-xs text-muted-foreground leading-tight mt-0.5">{POD_DESCRIPTIONS[p]}</span>
            </button>
          ))}
        </div>
        {form.formState.errors.pod && (
          <p className="text-sm text-destructive mt-2" role="alert">{form.formState.errors.pod.message}</p>
        )}
      </div>

      {/* Region selection */}
      <div>
        <h2 className="text-lg font-semibold mb-1">Region</h2>
        <p className="text-sm text-muted-foreground mb-4">Select one or more regions this request applies to.</p>
        <div className="grid grid-cols-3 gap-2">
          {REGIONS.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => toggleRegion(r as Region)}
              className={cn(
                'flex flex-col items-start rounded-lg border-2 px-4 py-3 text-left transition-all hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                regions.includes(r as Region) ? 'border-primary bg-primary/5' : 'border-border'
              )}
              aria-pressed={regions.includes(r as Region)}
            >
              <span className="font-semibold text-sm">{r}</span>
              <span className="text-xs text-muted-foreground leading-tight mt-0.5">{REGION_LABELS[r]}</span>
            </button>
          ))}
        </div>
        {form.formState.errors.region && (
          <p className="text-sm text-destructive mt-2" role="alert">{form.formState.errors.region.message}</p>
        )}
      </div>
    </div>
  )
}

// ── Step 2: Details ────────────────────────────────────────────────────────────

function Step2({ form }: { form: UseFormReturn<SubmitForm> }) {
  const isDefect = form.watch('request_type') === 'Defect'

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold">Tell us about the request</h2>

      <FormField control={form.control} name="title" render={({ field }) => (
        <FormItem>
          <FormLabel>Title <span className="text-destructive" aria-hidden>*</span></FormLabel>
          <FormControl><Input placeholder="Brief, descriptive title" {...field} /></FormControl>
          <FormMessage />
        </FormItem>
      )} />

      <FormField control={form.control} name="business_problem" render={({ field }) => (
        <FormItem>
          <FormLabel>Business Problem <span className="text-destructive" aria-hidden>*</span></FormLabel>
          <FormDescription>What problem does this solve? What is the current pain point?</FormDescription>
          <FormControl>
            <Textarea rows={4} placeholder="Describe the problem in detail…" className="resize-none" {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )} />

      {!isDefect && (
        <FormField control={form.control} name="expected_outcome" render={({ field }) => (
          <FormItem>
            <FormLabel>Expected Outcome</FormLabel>
            <FormDescription>What does success look like?</FormDescription>
            <FormControl>
              <Textarea rows={3} placeholder="Describe the desired outcome…" className="resize-none" {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )} />
      )}

      {isDefect && (
        <FormField control={form.control} name="steps_to_reproduce" render={({ field }) => (
          <FormItem>
            <FormLabel>Steps to Reproduce</FormLabel>
            <FormDescription>Step-by-step instructions to reproduce the issue.</FormDescription>
            <FormControl>
              <Textarea rows={4} placeholder={'1. Go to…\n2. Click on…\n3. Observe…'} className="resize-none" {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )} />
      )}

      <FormField control={form.control} name="affected_area" render={({ field }) => (
        <FormItem>
          <FormLabel>Affected Area <span className="text-destructive" aria-hidden>*</span></FormLabel>
          <FormDescription>Which product, feature, or system is impacted?</FormDescription>
          <FormControl>
            <Input placeholder="e.g. Driver app checkout flow, Charger firmware v4.2" {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )} />

      <FormField control={form.control} name="additional_context" render={({ field }) => (
        <FormItem>
          <FormLabel>Additional Context</FormLabel>
          <FormControl>
            <Textarea rows={3} placeholder="Any other relevant information, links, or context…" className="resize-none" {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )} />

    </div>
  )
}

// ── Step 3: File upload ────────────────────────────────────────────────────────

interface Step3Props {
  files: File[]
  onFilesChange: (files: File[]) => void
}

function Step3({ files, onFilesChange }: Step3Props) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const addFiles = (incoming: File[]) => {
    const valid = incoming.filter(
      (f) => ALLOWED_FILE_TYPES.includes(f.type) && f.size <= MAX_FILE_SIZE_BYTES
    )
    onFilesChange([...files, ...valid])
  }

  const removeFile = (index: number) => {
    onFilesChange(files.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Attachments</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Add screenshots, logs, or documents that help describe the request. This step is optional.
        </p>
      </div>

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="File upload area — drop files or click to browse"
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => { e.preventDefault(); setIsDragging(false); addFiles(Array.from(e.dataTransfer.files)) }}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click() }}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          isDragging
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-primary/50 hover:bg-muted/50'
        )}
      >
        <Upload className="h-8 w-8 text-muted-foreground mb-2" aria-hidden />
        <p className="text-sm font-medium">Drop files here or click to browse</p>
        <p className="text-xs text-muted-foreground mt-1">PDF, images, Word, Excel, CSV · Max 25 MB each</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ALLOWED_FILE_TYPES.join(',')}
        onChange={(e) => { if (e.target.files) addFiles(Array.from(e.target.files)) }}
        className="sr-only"
        aria-hidden
      />

      {/* Selected files list */}
      {files.length > 0 && (
        <ul className="space-y-2" aria-label="Selected files">
          {files.map((file, i) => (
            <li key={`${file.name}-${i}`} className="flex items-center gap-3 rounded-md border px-3 py-2 text-sm">
              <File className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
              <div className="flex-1 min-w-0">
                <p className="truncate font-medium">{file.name}</p>
                <p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p>
              </div>
              <button
                type="button"
                onClick={() => removeFile(i)}
                aria-label={`Remove ${file.name}`}
                className="text-muted-foreground hover:text-destructive transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export function SubmitPage() {
  const [step, setStep] = useState(0)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const navigate = useNavigate()
  const { mutate: createRequest, isPending } = useCreateRequest()
  const { toast } = useToast()

  const form = useForm<SubmitForm>({
    resolver: zodResolver(submitSchema),
    defaultValues: {
      request_type: 'Feature',
      priority: 'Medium',
      region: ['NA'] as Region[],
      title: '',
      business_problem: '',
      affected_area: '',
    },
  })

  const validateStep = async (stepIndex: number): Promise<boolean> => {
    const fieldsPerStep: Array<Array<keyof SubmitForm>> = [
      ['request_type', 'priority', 'pod', 'region'],
      ['title', 'business_problem', 'affected_area'],
      [],
    ]
    return form.trigger(fieldsPerStep[stepIndex])
  }

  const handleNext = async () => {
    const valid = await validateStep(step)
    if (valid) setStep((s) => s + 1)
  }

  const onSubmit = (data: SubmitForm) => {
    const payload = {
      ...data,
      expected_outcome: data.expected_outcome || undefined,
      steps_to_reproduce: data.steps_to_reproduce || undefined,
      additional_context: data.additional_context || undefined,
    }
    createRequest(payload, {
      onSuccess: async (req) => {
        if (pendingFiles.length > 0) {
          setIsUploading(true)
          try {
            // Single batch call — backend accepts list[UploadFile] under "files"
            await filesApi.uploadMany(req.id, pendingFiles)
          } catch (err) {
            // Request was created successfully; surface the upload-only failure
            // so the user knows attachments didn't go through.
            const message = err instanceof Error ? err.message : 'Could not attach files'
            toast({
              title: 'Attachments failed to upload',
              description: `${message}. The request was created — open it from My Requests to retry attaching files.`,
              variant: 'destructive',
            })
          }
          setIsUploading(false)
        }
        navigate(`/confirm/${req.id}`)
      },
      onError: (err) =>
        toast({ title: 'Submission failed', description: err.message, variant: 'destructive' }),
    })
  }

  const isSubmitting = isPending || isUploading

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Submit a Tech Request</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Route your feature requests and defect reports to the right Engineering POD.
        </p>
      </div>

      <StepIndicator current={step} />

      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          // Prevent implicit-submit when the user presses Enter in any text
          // input on steps 0/1, or after focus lands on the Submit button via
          // step transition. Submission must be an explicit click.
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              const target = e.target as HTMLElement
              // Allow Enter inside textareas — they need newlines.
              if (target.tagName === 'TEXTAREA') return
              e.preventDefault()
            }
          }}
        >
          <Card>
            <CardContent className="pt-6">
              {step === 0 && <Step1 form={form} />}
              {step === 1 && <Step2 form={form} />}
              {step === 2 && (
                <Step3 files={pendingFiles} onFilesChange={setPendingFiles} />
              )}
            </CardContent>
          </Card>

          <div className="flex justify-between mt-4">
            {step > 0 ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => setStep((s) => s - 1)}
                className="gap-2"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
            ) : <div />}

            {step < STEPS.length - 1 ? (
              <Button type="button" onClick={() => void handleNext()} className="gap-2">
                Next
                <ArrowRight className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                type="button"
                disabled={isSubmitting}
                className="gap-2"
                onClick={() => void form.handleSubmit(onSubmit)()}
              >
                {isSubmitting ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    {isUploading ? 'Uploading files…' : 'Submitting…'}
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4" />
                    Submit Request
                  </>
                )}
              </Button>
            )}
          </div>
        </form>
      </Form>
    </div>
  )
}
