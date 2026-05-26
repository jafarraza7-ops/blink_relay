import { useEffect, useState } from 'react'
import { Loader2, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/components/ui/use-toast'
import { useUpdateRequest } from '@/hooks/useRequests'
import { cn } from '@/lib/utils'
import { PRIORITIES, REGIONS, REGION_LABELS } from '@/lib/constants'
import type { BlinkRequest, RequestUpdate, Priority, Region } from '@/lib/types'



interface EditRequestDialogProps {
  request: BlinkRequest
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface FormState {
  title: string
  priority: Priority
  region: Region[]
  business_problem: string
  expected_outcome: string
  steps_to_reproduce: string
  affected_area: string
  additional_context: string
}

const fromRequest = (req: BlinkRequest): FormState => ({
  title: req.title,
  priority: req.priority,
  region: Array.isArray(req.region) ? req.region : [req.region],
  business_problem: req.business_problem,
  expected_outcome: req.expected_outcome ?? '',
  steps_to_reproduce: req.steps_to_reproduce ?? '',
  affected_area: req.affected_area,
  additional_context: req.additional_context ?? '',
})

function buildPayload(initial: FormState, current: FormState): RequestUpdate {
  const payload: RequestUpdate = {}
  if (current.title !== initial.title) payload.title = current.title.trim()
  if (current.priority !== initial.priority) payload.priority = current.priority
  const regionChanged =
    current.region.length !== initial.region.length ||
    current.region.some((r) => !initial.region.includes(r))
  if (regionChanged) payload.region = current.region
  if (current.business_problem !== initial.business_problem) {
    payload.business_problem = current.business_problem.trim()
  }
  if (current.affected_area !== initial.affected_area) {
    payload.affected_area = current.affected_area.trim()
  }
  if (current.expected_outcome !== initial.expected_outcome) {
    payload.expected_outcome = current.expected_outcome.trim() || undefined
  }
  if (current.steps_to_reproduce !== initial.steps_to_reproduce) {
    payload.steps_to_reproduce = current.steps_to_reproduce.trim() || undefined
  }
  if (current.additional_context !== initial.additional_context) {
    payload.additional_context = current.additional_context.trim() || undefined
  }
  return payload
}

export function EditRequestDialog({ request, open, onOpenChange }: EditRequestDialogProps) {
  const { toast } = useToast()
  const { mutate: updateRequest, isPending } = useUpdateRequest(request.id)
  const [initial, setInitial] = useState<FormState>(() => fromRequest(request))
  const [form, setForm] = useState<FormState>(() => fromRequest(request))

  useEffect(() => {
    if (open) {
      const snapshot = fromRequest(request)
      setInitial(snapshot)
      setForm(snapshot)
    }
  }, [open, request])

  const requiredMissing =
    !form.title.trim() || !form.business_problem.trim() || !form.affected_area.trim()

  const payload = buildPayload(initial, form)
  const isDirty = Object.keys(payload).length > 0

  const handleSave = () => {
    if (requiredMissing) return
    if (!isDirty) {
      onOpenChange(false)
      return
    }
    updateRequest(payload, {
      onSuccess: () => {
        toast({ title: 'Request updated', description: 'Your changes have been saved.' })
        onOpenChange(false)
      },
      onError: (err) =>
        toast({ title: 'Could not save changes', description: err.message, variant: 'destructive' }),
    })
  }

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((s) => ({ ...s, [key]: value }))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit request</DialogTitle>
          <DialogDescription>
            Update the details below. Changes are visible to reviewers and logged in the
            request history.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="edit-title">
              Title <span className="text-destructive">*</span>
            </Label>
            <Input
              id="edit-title"
              value={form.title}
              onChange={(e) => update('title', e.target.value)}
              maxLength={200}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-priority">Priority</Label>
            <Select
              value={form.priority}
              onValueChange={(v) => update('priority', v as Priority)}
            >
              <SelectTrigger id="edit-priority">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PRIORITIES.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Region</Label>
            <div className="flex gap-2 flex-wrap">
              {REGIONS.map((r) => {
                const selected = form.region.includes(r as Region)
                return (
                  <button
                    key={r}
                    type="button"
                    onClick={() => {
                      const next = selected
                        ? form.region.filter((x) => x !== r)
                        : [...form.region, r as Region]
                      if (next.length > 0) update('region', next)
                    }}
                    className={cn(
                      'rounded-md border-2 px-4 py-2 text-sm font-medium transition-colors',
                      selected
                        ? 'border-primary bg-primary/5 text-primary'
                        : 'border-border hover:border-primary/50'
                    )}
                    aria-pressed={selected}
                  >
                    {r} <span className="font-normal text-muted-foreground">· {REGION_LABELS[r as Region]}</span>
                  </button>
                )
              })}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-business-problem">
              Business problem <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="edit-business-problem"
              value={form.business_problem}
              onChange={(e) => update('business_problem', e.target.value)}
              rows={4}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-affected-area">
              Affected area <span className="text-destructive">*</span>
            </Label>
            <Input
              id="edit-affected-area"
              value={form.affected_area}
              onChange={(e) => update('affected_area', e.target.value)}
            />
          </div>

          {request.request_type === 'Feature' ? (
            <div className="space-y-1.5">
              <Label htmlFor="edit-expected-outcome">Expected outcome</Label>
              <Textarea
                id="edit-expected-outcome"
                value={form.expected_outcome}
                onChange={(e) => update('expected_outcome', e.target.value)}
                rows={3}
              />
            </div>
          ) : (
            <div className="space-y-1.5">
              <Label htmlFor="edit-steps">Steps to reproduce</Label>
              <Textarea
                id="edit-steps"
                value={form.steps_to_reproduce}
                onChange={(e) => update('steps_to_reproduce', e.target.value)}
                rows={3}
              />
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="edit-additional-context">Additional context</Label>
            <Textarea
              id="edit-additional-context"
              value={form.additional_context}
              onChange={(e) => update('additional_context', e.target.value)}
              rows={3}
            />
          </div>

        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={isPending || requiredMissing}
            className="gap-2"
          >
            {isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving…
              </>
            ) : (
              <>
                <Save className="h-4 w-4" />
                Save changes
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
