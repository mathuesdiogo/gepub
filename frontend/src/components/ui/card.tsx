import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-xl2 border border-slate-200/80 bg-white/95 shadow-panel backdrop-blur-sm',
        className,
      )}
      {...props}
    />
  )
}
