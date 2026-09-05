<script setup>
/**
 * The next-dollar waterfall.
 *
 * This ordering comes from the backend's rules engine, not from a model — which
 * is why each step can state plainly why it sits where it does.
 */
import { money0 } from "@/lib/format";
import Badge from "@/components/ui/Badge.vue";

defineProps({
  steps: { type: Array, default: () => [] },
  limit: { type: Number, default: 0 },
});

const STATUS = {
  urgent: { label: "Urgent", variant: "critical" },
  not_started: { label: "Not started", variant: "warning" },
  in_progress: { label: "In progress", variant: "primary" },
  queued: { label: "Next up", variant: "neutral" },
  ready: { label: "Ready", variant: "good" },
  blocked: { label: "Later", variant: "neutral" },
  check: { label: "Check", variant: "neutral" },
};
</script>

<template>
  <ol class="space-y-3">
    <li
      v-for="step in (limit ? steps.slice(0, limit) : steps)"
      :key="step.key"
      class="flex gap-3 rounded-lg border border-line bg-card p-3.5"
    >
      <span
        class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold"
        :class="step.status === 'blocked' || step.status === 'check'
          ? 'bg-raised text-ink-subtle'
          : 'bg-[color:var(--primary-soft)] text-primary'"
        aria-hidden="true"
      >{{ step.rank }}</span>

      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <p class="text-[13.5px] font-semibold text-ink">{{ step.title }}</p>
          <Badge :variant="STATUS[step.status]?.variant ?? 'neutral'" size="sm">
            {{ STATUS[step.status]?.label ?? step.status }}
          </Badge>
        </div>
        <p class="mt-1 text-[12.5px] leading-relaxed text-ink-muted">{{ step.why }}</p>
        <p v-if="step.suggested_monthly > 0" class="mt-1.5 text-[12px] font-medium text-ink tabular">
          Suggested: {{ money0(step.suggested_monthly) }}/month
        </p>
      </div>
    </li>
  </ol>
</template>
