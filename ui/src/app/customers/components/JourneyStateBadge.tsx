import { Badge } from '@/components/ui/badge';
import { JOURNEY_STATE_LABELS } from '@/lib/customerTimelineApi';
import { cn } from '@/lib/utils';

const STATE_STYLES: Record<string, string> = {
  payment_completed: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30',
  payment_failed: 'bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/30',
  payment_pending: 'bg-amber-500/15 text-amber-800 dark:text-amber-200 border-amber-500/30',
  whatsapp_follow_up: 'bg-sky-500/15 text-sky-800 dark:text-sky-200 border-sky-500/30',
  email_follow_up: 'bg-cyan-500/15 text-cyan-800 dark:text-cyan-200 border-cyan-500/30',
  escalated: 'bg-orange-500/15 text-orange-800 dark:text-orange-200 border-orange-500/30',
  campaign_retry: 'bg-violet-500/15 text-violet-800 dark:text-violet-200 border-violet-500/30',
  voice_active: 'bg-blue-500/15 text-blue-800 dark:text-blue-200 border-blue-500/30',
  orchestration_waiting: 'bg-indigo-500/15 text-indigo-800 dark:text-indigo-200 border-indigo-500/30',
};

export function JourneyStateBadge({ state }: { state: string }) {
  const label = JOURNEY_STATE_LABELS[state] ?? state.replace(/_/g, ' ');
  return (
    <Badge
      variant="outline"
      className={cn('font-medium capitalize', STATE_STYLES[state] ?? '')}
    >
      {label}
    </Badge>
  );
}
