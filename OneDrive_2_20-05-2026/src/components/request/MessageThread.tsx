import { useState } from 'react'
import { Send } from 'lucide-react'

const BODY_LIMIT = 200

export function TruncatedBody({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false)
  if (text.length <= BODY_LIMIT) return <p className="whitespace-pre-wrap">{text}</p>
  return (
    <p className="whitespace-pre-wrap">
      {expanded ? text : `${text.slice(0, BODY_LIMIT)}…`}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="ml-1 text-xs font-medium underline opacity-70 hover:opacity-100"
      >
        {expanded ? 'Show less' : 'Read more'}
      </button>
    </p>
  )
}

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useThread, usePostMessage } from '@/hooks/useThread'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/components/ui/use-toast'
import { formatDateTime } from '@/lib/utils'
import { cn } from '@/lib/utils'

interface MessageThreadProps {
  requestId: string
  internalOnly?: boolean
}

function getInitials(name: string): string {
  return name.split(' ').map((n) => n[0]).slice(0, 2).join('').toUpperCase()
}

export function MessageThread({ requestId, internalOnly = false }: MessageThreadProps) {
  const { data: messages = [], isLoading } = useThread(requestId)
  const { mutate: postMessage, isPending } = usePostMessage(requestId)
  const { user } = useAuth()
  const { toast } = useToast()
  const [body, setBody] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!body.trim()) return
    postMessage(
      { body: body.trim(), is_internal: internalOnly },
      {
        onSuccess: () => setBody(''),
        onError: (err) => toast({ title: 'Failed to send message', description: err.message, variant: 'destructive' }),
      }
    )
  }

  if (isLoading) {
    return <div className="flex items-center justify-center py-8"><div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Messages */}
      <div className="space-y-4">
        {messages.length === 0 && (
          <p className="text-center text-sm text-muted-foreground py-6">No messages yet</p>
        )}
        {messages.map((msg) => {
          const isOwn = msg.author_email === user?.email
          const isClarificationQ = msg.message_type === 'clarification_question'
          const isClarificationR = msg.message_type === 'clarification_response'
          const isStatusChange = msg.message_type === 'status_change'

          if (isStatusChange) {
            return (
              <div key={msg.id} className="flex flex-col items-center gap-1 py-1">
                <div className="flex items-center gap-3 w-full">
                  <div className="flex-1 border-t border-dashed border-muted-foreground/30" />
                  <div className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs text-blue-700 text-center whitespace-pre-wrap max-w-[70%]">
                    {msg.body}
                  </div>
                  <div className="flex-1 border-t border-dashed border-muted-foreground/30" />
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {msg.author_name} · {formatDateTime(msg.created_at)}
                </p>
              </div>
            )
          }

          return (
            <div
              key={msg.id}
              className={cn(
                'flex gap-3',
                msg.is_internal && 'opacity-75',
                isOwn && 'flex-row-reverse'
              )}
            >
              <Avatar className="h-8 w-8 shrink-0">
                <AvatarFallback className="bg-muted text-xs">
                  {getInitials(msg.author_name)}
                </AvatarFallback>
              </Avatar>
              <div className={cn('max-w-[75%] space-y-1', isOwn && 'items-end flex flex-col')}>
                <div className={cn(
                  'rounded-lg px-3 py-2 text-sm',
                  isClarificationQ
                    ? 'bg-blue-50 border border-blue-200 text-blue-900'
                    : isClarificationR
                    ? 'bg-teal-50 border border-teal-200 text-teal-900'
                    : isOwn
                    ? 'bg-primary text-primary-foreground'
                    : msg.is_internal
                    ? 'bg-amber-50 border border-amber-200 text-amber-900'
                    : 'bg-muted text-foreground'
                )}>
                  <TruncatedBody text={msg.body} />
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span>{msg.author_name}</span>
                  {isClarificationQ && <span className="rounded bg-blue-100 px-1 text-blue-700">Clarification Request</span>}
                  {isClarificationR && <span className="rounded bg-teal-100 px-1 text-teal-700">Clarification Response</span>}
                  {msg.is_internal && !isClarificationQ && !isClarificationR && (
                    <span className="rounded bg-amber-100 px-1 text-amber-700">Internal</span>
                  )}
                  <span>·</span>
                  <span>{formatDateTime(msg.created_at)}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Compose */}
      <form onSubmit={handleSubmit} className="space-y-2 border-t pt-4">
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Write a message…"
          rows={3}
          className="resize-none"
        />
        <div className="flex items-center justify-between">
          {internalOnly && (
            <span className="text-xs text-muted-foreground">Internal note — not visible to requestor</span>
          )}
          <Button type="submit" size="sm" disabled={!body.trim() || isPending} className="ml-auto">
            <Send className="mr-2 h-4 w-4" />
            Send
          </Button>
        </div>
      </form>
    </div>
  )
}
