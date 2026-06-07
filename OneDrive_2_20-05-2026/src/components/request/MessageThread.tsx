import { useState, useRef } from 'react'
import { Send } from 'lucide-react'

const BODY_LIMIT = 200

export function TruncatedBody({ text }: { text: string }) {
  // IMPROVEMENT: Add text wrapping for long unbroken text (e.g., URLs)
  // Prevents message content from breaking container layout
  // Classes:
  //   - whitespace-pre-wrap: preserve line breaks from user input
  //   - break-words: break long words/URLs to fit container
  //   - overflow-hidden: clip text that exceeds container bounds
  const [expanded, setExpanded] = useState(false)
  if (text.length <= BODY_LIMIT) return <p className="whitespace-pre-wrap break-words overflow-hidden">{text}</p>
  return (
    <p className="whitespace-pre-wrap break-words overflow-hidden">
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
import { usersApi } from '@/lib/api'

interface MessageThreadProps {
  requestId: string
  internalOnly?: boolean
}

interface UserSuggestion {
  oid: string
  email: string
  display_name: string
}

function getInitials(name: string): string {
  return name.split(' ').map((n) => n[0]).slice(0, 2).join('').toUpperCase()
}

export function MessageThread({ requestId, internalOnly = false }: MessageThreadProps) {
  const { data: messages = [], isLoading } = useThread(requestId)
  const { mutate: postMessage, isPending } = usePostMessage(requestId)
  const { user } = useAuth()
  const isPM = user?.roles?.includes('ProductManager') || user?.roles?.includes('Admin')
  const { toast } = useToast()
  const [body, setBody] = useState('')
  const [isInternal, setIsInternal] = useState(internalOnly)
  const [mentions, setMentions] = useState<string[]>([])
  const [suggestions, setSuggestions] = useState<UserSuggestion[]>([])
  const [mentionQuery, setMentionQuery] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const getMentionContext = (text: string, cursorPos: number) => {
    const beforeCursor = text.substring(0, cursorPos)
    const lastAtIndex = beforeCursor.lastIndexOf('@')

    if (lastAtIndex === -1) return null

    const afterAt = beforeCursor.substring(lastAtIndex + 1)
    if (afterAt.includes(' ')) return null

    return { query: afterAt, atIndex: lastAtIndex }
  }

  const handleBodyChange = async (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newBody = e.target.value
    const cursorPos = e.target.selectionStart
    setBody(newBody)

    const context = getMentionContext(newBody, cursorPos)
    if (context && context.query.length > 0) {
      setMentionQuery(context.query)
      setShowSuggestions(true)
      try {
        const users = await usersApi.list(context.query)
        const filtered = users.filter(u => !mentions.includes(u.oid))
        setSuggestions(filtered)
      } catch (err) {
        setSuggestions([])
      }
    } else {
      setShowSuggestions(false)
      setSuggestions([])
    }
  }

  const handleUserSelect = (user: UserSuggestion) => {
    const cursorPos = textareaRef.current?.selectionStart || 0
    const beforeCursor = body.substring(0, cursorPos)
    const lastAtIndex = beforeCursor.lastIndexOf('@')

    if (lastAtIndex === -1) return

    const beforeAt = body.substring(0, lastAtIndex)
    const afterCursor = body.substring(cursorPos)

    const newBody = beforeAt + '@' + afterCursor
    setBody(newBody)
    setMentions([...mentions, user.oid])
    setShowSuggestions(false)
    setSuggestions([])
    setMentionQuery('')
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    // Validate message is not empty or whitespace-only
    if (!body || !body.trim()) {
      toast({
        title: 'Invalid Message',
        description: 'Message cannot be empty or contain only spaces',
        variant: 'destructive',
      })
      return
    }

    // Sanitize and send
    postMessage(
      { body: body.trim(), is_internal: isInternal, mentions },
      {
        onSuccess: () => {
          setBody('')
          setMentions([])
          toast({ title: 'Message sent' })
        },
        onError: (err) => toast({ title: 'Failed to send message', description: err.message, variant: 'destructive' }),
      }
    )
  }

  if (isLoading) {
    return <div className="flex items-center justify-center py-8"><div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>
  }

  return (
    <div className="flex flex-col gap-4">
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
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground flex-wrap">
                  <span>{msg.author_name}</span>
                  {isClarificationQ && <span className="rounded bg-blue-100 px-1 text-blue-700">Clarification Request</span>}
                  {isClarificationR && <span className="rounded bg-teal-100 px-1 text-teal-700">Clarification Response</span>}
                  {msg.is_internal && !isClarificationQ && !isClarificationR && (
                    <span className="rounded bg-amber-100 px-1 text-amber-700">Internal</span>
                  )}
                  {msg.mentions && msg.mentions.length > 0 && (
                    <>
                      <span>·</span>
                      <div className="flex gap-0.5 flex-wrap">
                        {msg.mentions.map((oid) => (
                          <span key={oid} className="rounded bg-blue-50 px-1 text-blue-700">
                            @{oid.slice(0, 8)}
                          </span>
                        ))}
                      </div>
                    </>
                  )}
                  <span>·</span>
                  <span>{formatDateTime(msg.created_at)}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <form onSubmit={handleSubmit} className="space-y-2 border-t pt-4">
        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={body}
            onChange={handleBodyChange}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
            placeholder="Write a message… (Use @username to mention someone)"
            rows={3}
            className="resize-none"
          />
          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute bottom-full left-0 right-0 mb-1 border border-muted-foreground/30 rounded-md bg-white shadow-lg z-10">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion.oid}
                  type="button"
                  onClick={() => handleUserSelect(suggestion)}
                  className="w-full text-left px-3 py-2 hover:bg-muted text-sm border-b last:border-b-0 flex flex-col gap-0.5"
                >
                  <span className="font-medium">{suggestion.display_name}</span>
                  <span className="text-xs text-muted-foreground">{suggestion.email}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 flex-wrap">
            {isPM && (
              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                <input
                  type="checkbox"
                  checked={isInternal}
                  onChange={(e) => setIsInternal(e.target.checked)}
                  className="rounded border border-muted-foreground"
                />
                <span>{isInternal ? 'Internal note — not visible to requestor' : 'Visible to requestor'}</span>
              </label>
            )}
            {!isPM && internalOnly && (
              <span className="text-xs text-amber-600 font-medium">ℹ️ Internal note — not visible to requestor</span>
            )}
            {mentions.length > 0 && (
              <div className="flex gap-1">
                {mentions.map((oid) => (
                  <span
                    key={oid}
                    className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-1 text-xs text-blue-700"
                  >
                    @{oid.slice(0, 8)}
                    <button
                      type="button"
                      onClick={() => setMentions(mentions.filter((m) => m !== oid))}
                      className="hover:text-blue-900"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
          <Button type="submit" size="sm" disabled={!body.trim() || isPending} className="ml-auto">
            <Send className="mr-2 h-4 w-4" />
            Send
          </Button>
        </div>
      </form>
    </div>
  )
}
