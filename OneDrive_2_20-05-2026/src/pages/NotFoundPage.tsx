import { Link } from 'react-router-dom'
import { ArrowLeft, SearchX } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <SearchX className="h-16 w-16 text-muted-foreground/50" />
      <div>
        <h1 className="text-3xl font-bold">404</h1>
        <p className="text-xl font-medium mt-1">Page not found</p>
        <p className="text-muted-foreground mt-2 max-w-sm">
          The page you&apos;re looking for doesn&apos;t exist or you may not have permission to view it.
        </p>
      </div>
      <Button asChild variant="outline">
        <Link to="/">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to home
        </Link>
      </Button>
    </div>
  )
}
