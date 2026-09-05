<script setup>
/**
 * Grouped bars for period comparison (income vs expenses by month).
 * Bars share one y-axis and sit 2px apart so adjacent fills stay separable.
 */
import { computed, ref } from "vue";
import { moneyCompact, money0 } from "@/lib/format";
import ChartLegend from "./ChartLegend.vue";

const props = defineProps({
  /** [{ label, color }] */
  series: { type: Array, default: () => [] },
  /** [{ label, values: [n, n] }] */
  groups: { type: Array, default: () => [] },
  height: { type: Number, default: 220 },
  formatY: { type: Function, default: moneyCompact },
  formatTooltip: { type: Function, default: money0 },
});

const W = 720;
const PAD = { top: 12, right: 16, bottom: 28, left: 52 };
const hover = ref(null);

const inner = computed(() => ({ w: W - PAD.left - PAD.right, h: props.height - PAD.top - PAD.bottom }));

const max = computed(() => {
  const all = props.groups.flatMap((g) => g.values.map(Number));
  return Math.max(...all, 1) * 1.08;
});

const bandWidth = computed(() => inner.value.w / Math.max(props.groups.length, 1));
const barWidth = computed(() => {
  const usable = bandWidth.value * 0.62;
  return Math.max(4, (usable - 2 * (props.series.length - 1)) / Math.max(props.series.length, 1));
});

function barX(groupIndex, seriesIndex) {
  const groupStart = PAD.left + groupIndex * bandWidth.value;
  const total = barWidth.value * props.series.length + 2 * (props.series.length - 1);
  const offset = (bandWidth.value - total) / 2;
  return groupStart + offset + seriesIndex * (barWidth.value + 2);
}

function barHeight(value) {
  return Math.max(0, (Number(value) / max.value) * inner.value.h);
}

const ticks = computed(() => Array.from({ length: 4 }, (_, i) => (max.value / 3) * i));
const legendItems = computed(() => props.series.map((s) => ({ label: s.label, color: s.color })));
</script>

<template>
  <div class="w-full">
    <div class="relative">
      <svg :viewBox="`0 0 ${W} ${height}`" class="w-full" :style="{ height: `${height}px` }"
        role="img" aria-label="Grouped bar chart">
        <line
          v-for="(tick, i) in ticks" :key="`g${i}`"
          :x1="PAD.left" :x2="W - PAD.right"
          :y1="PAD.top + inner.h - barHeight(tick)" :y2="PAD.top + inner.h - barHeight(tick)"
          stroke="var(--grid)" stroke-width="1"
        />
        <text
          v-for="(tick, i) in ticks" :key="`t${i}`"
          :x="PAD.left - 8" :y="PAD.top + inner.h - barHeight(tick) + 4"
          text-anchor="end" font-size="11" fill="var(--ink-subtle)" class="tabular"
        >{{ formatY(tick) }}</text>

        <g v-for="(group, gi) in groups" :key="group.label">
          <rect
            :x="PAD.left + gi * bandWidth" :y="PAD.top" :width="bandWidth" :height="inner.h"
            fill="transparent" @mouseenter="hover = gi" @mouseleave="hover = null"
          />
          <rect
            v-for="(s, si) in series" :key="`${group.label}-${s.label}`"
            :x="barX(gi, si)"
            :y="PAD.top + inner.h - barHeight(group.values[si])"
            :width="barWidth"
            :height="barHeight(group.values[si])"
            :fill="s.color"
            rx="4"
            :opacity="hover === null || hover === gi ? 1 : 0.45"
            class="transition-opacity"
          />
        </g>

        <line :x1="PAD.left" :x2="W - PAD.right" :y1="PAD.top + inner.h" :y2="PAD.top + inner.h"
          stroke="var(--axis)" stroke-width="1" />

        <text
          v-for="(group, gi) in groups" :key="`x${group.label}`"
          :x="PAD.left + gi * bandWidth + bandWidth / 2" :y="height - 9"
          text-anchor="middle" font-size="11"
          :fill="hover === gi ? 'var(--ink)' : 'var(--ink-subtle)'"
        >{{ group.label }}</text>
      </svg>

      <div
        v-if="hover !== null"
        class="pointer-events-none absolute top-2 z-10 min-w-[9rem] rounded-lg border border-line bg-card p-2.5 shadow-pop"
        :style="hover > groups.length / 2 ? { left: '3.5rem' } : { right: '0.5rem' }"
      >
        <p class="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-subtle">
          {{ groups[hover].label }}
        </p>
        <div v-for="(s, si) in series" :key="`tt-${s.label}`" class="flex items-center justify-between gap-4 py-0.5">
          <span class="flex items-center gap-1.5 text-[12px] text-ink-muted">
            <span class="h-2 w-2 rounded-[2px]" :style="{ backgroundColor: s.color }" />
            {{ s.label }}
          </span>
          <span class="text-[12px] font-semibold text-ink tabular">
            {{ formatTooltip(groups[hover].values[si]) }}
          </span>
        </div>
      </div>
    </div>

    <ChartLegend v-if="series.length > 1" :items="legendItems" class="mt-3 pl-[52px]" />
  </div>
</template>
