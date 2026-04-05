import { Database } from 'lucide-react'

export default function NoData({ message = 'Awaiting first data run' }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-text-dim">
      <Database size={28} className="mb-2 opacity-40" />
      <span className="text-sm">{message}</span>
    </div>
  )
}
