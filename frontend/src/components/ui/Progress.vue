<script setup>
import { computed } from "vue";

const props = defineProps({
  value: { type: Number, default: 0 },
  max: { type: Number, default: 100 },
  /** Colour role: primary | good | warning | critical */
  tone: { type: String, default: "primary" },
  label: String,
  size: { type: String, default: "md" }, // sm | md
});

const pct = computed(() => Math.max(0, Math.min(100, (props.value / (props.max || 1)) * 100)));
const TONES = {
  primary: "var(--primary)",
  good: "var(--good)",
  warning: "var(--warning)",
  critical: "var(--critical)",
};
const color = computed(() => TONES[props.tone] ?? TONES.primary);
</script>

<template>
  <div
    class="w-full overflow-hidden rounded-full bg-raised"
    :class="size === 'sm' ? 'h-1.5' : 'h-2.5'"
    role="progressbar"
    :aria-valuenow="Math.round(value)"
    aria-valuemin="0"
    :aria-valuemax="max"
    :aria-label="label"
  >
    <!-- 4px rounded data-end, anchored to the track start. -->
    <div
      class="h-full rounded-full transition-all duration-500"
      :style="{ width: `${pct}%`, backgroundColor: color }"
    />
  </div>
</template>
