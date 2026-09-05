<script setup>
/**
 * A headline figure. The number is the message, so it is the largest element and
 * everything else is support. No plot unless a trend is genuinely available.
 */
import Sparkline from "@/components/charts/Sparkline.vue";

defineProps({
  label: { type: String, required: true },
  value: { type: String, required: true },
  /** Short clause under the value, e.g. "3.2 months covered". */
  detail: String,
  /** { text, direction: 'up' | 'down' | 'flat', good: Boolean } */
  delta: Object,
  trend: { type: Array, default: () => [] },
  trendColor: { type: String, default: "var(--primary)" },
  /** Explains where the number came from, for the "why" question. */
  footnote: String,
});
</script>

<template>
  <div class="rounded-xl border border-line bg-card p-4 shadow-card sm:p-5">
    <div class="flex items-start justify-between gap-3">
      <p class="text-[13px] font-medium text-ink-muted">{{ label }}</p>
      <Sparkline v-if="trend.length > 1" :values="trend" :color="trendColor" />
    </div>

    <p class="mt-2 text-[26px] font-semibold leading-none tracking-tight text-ink sm:text-[28px]">
      {{ value }}
    </p>

    <div v-if="detail || delta" class="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
      <!-- The arrow glyph carries direction; colour only reinforces it. -->
      <span
        v-if="delta"
        class="inline-flex items-center gap-0.5 text-[12px] font-medium"
        :style="{ color: delta.good ? 'var(--good-ink)' : 'var(--critical-ink)' }"
      >
        <svg class="h-3 w-3" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path
            :d="delta.direction === 'up' ? 'M6 10V2m0 0L2.5 5.5M6 2l3.5 3.5' : delta.direction === 'down' ? 'M6 2v8m0 0 3.5-3.5M6 10 2.5 6.5' : 'M2 6h8'"
            stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"
          />
        </svg>
        {{ delta.text }}
      </span>
      <span v-if="detail" class="text-[12px] text-ink-muted">{{ detail }}</span>
    </div>

    <p v-if="footnote" class="mt-2 text-[11px] leading-snug text-ink-subtle">{{ footnote }}</p>
  </div>
</template>
