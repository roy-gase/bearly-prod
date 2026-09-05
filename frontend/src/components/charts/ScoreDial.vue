<script setup>
/**
 * The financial health score as a single arc.
 *
 * A hero number with a magnitude ring — the score is the message, so it is the
 * largest thing in the component and the arc only supports it.
 */
import { computed } from "vue";
import { statusColor, scoreStatus } from "@/lib/colors";

const props = defineProps({
  score: { type: Number, default: 0 },
  grade: { type: String, default: "" },
  size: { type: Number, default: 132 },
});

const R = 54;
const CIRC = 2 * Math.PI * R;
const dash = computed(() => (Math.max(0, Math.min(100, props.score)) / 100) * CIRC);
const color = computed(() => statusColor(scoreStatus(props.score)));
</script>

<template>
  <div class="flex flex-col items-center">
    <div class="relative" :style="{ width: `${size}px`, height: `${size}px` }">
      <svg viewBox="0 0 128 128" class="h-full w-full -rotate-90">
        <circle cx="64" cy="64" :r="R" fill="none" stroke="var(--raised)" stroke-width="10" />
        <circle
          cx="64" cy="64" :r="R" fill="none" :stroke="color" stroke-width="10" stroke-linecap="round"
          :stroke-dasharray="`${dash} ${CIRC}`"
          class="transition-all duration-700"
        />
      </svg>
      <div class="absolute inset-0 flex flex-col items-center justify-center">
        <span class="text-[34px] font-semibold leading-none text-ink">{{ Math.round(score) }}</span>
        <span class="mt-0.5 text-[11px] text-ink-subtle">out of 100</span>
      </div>
    </div>
    <!-- The grade is spelled out: the arc colour is never the only signal. -->
    <p v-if="grade" class="mt-2 text-sm font-semibold text-ink">{{ grade }}</p>
  </div>
</template>
