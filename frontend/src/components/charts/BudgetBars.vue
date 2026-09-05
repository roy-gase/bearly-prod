<script setup>
/**
 * Budget versus actual, one row per category.
 *
 * The plan is a recessive track; actual spending is the solid mark drawn on top,
 * so overspend reads as the bar crossing the plan marker rather than as a colour
 * the reader has to decode.
 */
import { money0, percent } from "@/lib/format";

defineProps({
  /** [{ name, budgeted, actual, remaining, used_pct, is_over }] */
  rows: { type: Array, default: () => [] },
  limit: { type: Number, default: 0 },
});
</script>

<template>
  <ul class="space-y-3.5">
    <li v-for="row in (limit ? rows.slice(0, limit) : rows)" :key="row.name">
      <div class="mb-1.5 flex items-baseline justify-between gap-3">
        <span class="truncate text-[13px] font-medium text-ink">{{ row.name }}</span>
        <span class="shrink-0 text-[12px] tabular">
          <span :class="row.is_over ? 'font-semibold text-[color:var(--critical-ink)]' : 'text-ink'">
            {{ money0(row.actual) }}
          </span>
          <span class="text-ink-subtle"> / {{ money0(row.budgeted) }}</span>
        </span>
      </div>

      <div class="relative h-2.5 w-full overflow-hidden rounded-full bg-raised">
        <div
          class="h-full rounded-full transition-all duration-500"
          :style="{
            width: `${Math.min(100, row.budgeted > 0 ? row.used_pct : 100)}%`,
            backgroundColor: row.is_over ? 'var(--critical)' : 'var(--primary)',
          }"
        />
      </div>

      <p class="mt-1 text-[11px] text-ink-muted">
        <template v-if="row.budgeted === 0">Unbudgeted spending</template>
        <template v-else-if="row.is_over">
          {{ money0(Math.abs(row.remaining)) }} over plan · {{ percent(row.used_pct) }} used
        </template>
        <template v-else>
          {{ money0(row.remaining) }} left · {{ percent(row.used_pct) }} used
        </template>
      </p>
    </li>
  </ul>
</template>
