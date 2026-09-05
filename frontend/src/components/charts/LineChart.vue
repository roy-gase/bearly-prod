<script setup>
/**
 * Multi-series line chart with a crosshair and tooltip.
 *
 * One y-axis only — a second scale would let two series be compared that are
 * not comparable. Series that differ in magnitude belong in separate charts.
 */
import { computed, ref } from "vue";
import { moneyCompact, money0 } from "@/lib/format";
import ChartLegend from "./ChartLegend.vue";

const props = defineProps({
  /** [{ label, color, points: [{ x, y }] }] — x values must align across series. */
  series: { type: Array, default: () => [] },
  /** Tick labels, one per x index. */
  labels: { type: Array, default: () => [] },
  height: { type: Number, default: 220 },
  formatY: { type: Function, default: moneyCompact },
  formatTooltip: { type: Function, default: money0 },
  /** Draw a zero baseline when the data crosses it. */
  showZero: { type: Boolean, default: true },
  area: Boolean,
});

const W = 720;
const PAD = { top: 12, right: 16, bottom: 26, left: 52 };
const hover = ref(null);

const inner = computed(() => ({
  w: W - PAD.left - PAD.right,
  h: props.height - PAD.top - PAD.bottom,
}));

const count = computed(() => Math.max(...props.series.map((s) => s.points.length), 0));

const bounds = computed(() => {
  const values = props.series.flatMap((s) => s.points.map((p) => Number(p.y) || 0));
  if (!values.length) return { min: 0, max: 1 };
  let min = Math.min(...values, props.showZero ? 0 : Infinity);
  let max = Math.max(...values, 0);
  if (min === max) max = min + 1;
  const pad = (max - min) * 0.08;
  return { min: min - (min < 0 ? pad : 0), max: max + pad };
});

function xAt(index) {
  if (count.value <= 1) return PAD.left + inner.value.w / 2;
  return PAD.left + (index / (count.value - 1)) * inner.value.w;
}

function yAt(value) {
  const { min, max } = bounds.value;
  const ratio = (Number(value) - min) / (max - min || 1);
  return PAD.top + inner.value.h - ratio * inner.value.h;
}

function pathFor(points) {
  return points.map((p, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(1)},${yAt(p.y).toFixed(1)}`).join(" ");
}

function areaFor(points) {
  if (!points.length) return "";
  const base = yAt(Math.max(bounds.value.min, 0));
  return `${pathFor(points)} L${xAt(points.length - 1).toFixed(1)},${base.toFixed(1)} L${xAt(0).toFixed(1)},${base.toFixed(1)} Z`;
}

const ticks = computed(() => {
  const { min, max } = bounds.value;
  return Array.from({ length: 4 }, (_, i) => min + ((max - min) / 3) * i);
});

const zeroY = computed(() =>
  bounds.value.min < 0 && bounds.value.max > 0 ? yAt(0) : null,
);

function onMove(event) {
  const svg = event.currentTarget;
  const rect = svg.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / rect.width) * W;
  const ratio = (x - PAD.left) / inner.value.w;
  const index = Math.round(ratio * (count.value - 1));
  hover.value = index >= 0 && index < count.value ? index : null;
}

const legendItems = computed(() => props.series.map((s) => ({ label: s.label, color: s.color })));
const tooltipSide = computed(() => (hover.value > count.value / 2 ? "right" : "left"));
</script>

<template>
  <div class="w-full">
    <div class="relative">
      <svg
        :viewBox="`0 0 ${W} ${height}`"
        class="w-full touch-none"
        :style="{ height: `${height}px` }"
        role="img"
        :aria-label="`Line chart with ${series.length} series`"
        @mousemove="onMove"
        @mouseleave="hover = null"
      >
        <!-- Recessive gridlines -->
        <g>
          <line
            v-for="(tick, i) in ticks"
            :key="`g${i}`"
            :x1="PAD.left" :x2="W - PAD.right"
            :y1="yAt(tick)" :y2="yAt(tick)"
            stroke="var(--grid)" stroke-width="1"
          />
        </g>

        <!-- Zero baseline sits above the grid when values cross it -->
        <line
          v-if="zeroY !== null"
          :x1="PAD.left" :x2="W - PAD.right" :y1="zeroY" :y2="zeroY"
          stroke="var(--axis)" stroke-width="1.5"
        />

        <text
          v-for="(tick, i) in ticks"
          :key="`t${i}`"
          :x="PAD.left - 8" :y="yAt(tick) + 4"
          text-anchor="end" font-size="11" fill="var(--ink-subtle)"
          class="tabular"
        >{{ formatY(tick) }}</text>

        <g v-if="area">
          <path
            v-for="s in series" :key="`a-${s.label}`"
            :d="areaFor(s.points)" :fill="s.color" opacity="0.10"
          />
        </g>

        <!-- 2px lines, round joins -->
        <path
          v-for="s in series" :key="`l-${s.label}`"
          :d="pathFor(s.points)" fill="none" :stroke="s.color"
          stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
        />

        <g v-if="hover !== null">
          <line
            :x1="xAt(hover)" :x2="xAt(hover)" :y1="PAD.top" :y2="PAD.top + inner.h"
            stroke="var(--axis)" stroke-width="1" stroke-dasharray="3 3"
          />
          <!-- 2px surface ring keeps markers legible where series overlap -->
          <circle
            v-for="s in series" :key="`m-${s.label}`"
            v-show="s.points[hover]"
            :cx="xAt(hover)" :cy="yAt(s.points[hover]?.y ?? 0)" r="4.5"
            :fill="s.color" stroke="var(--card)" stroke-width="2"
          />
        </g>

        <text
          v-for="(label, i) in labels" :key="`x${i}`"
          v-show="labels.length <= 8 || i % Math.ceil(labels.length / 8) === 0"
          :x="xAt(i)" :y="height - 8"
          text-anchor="middle" font-size="11" fill="var(--ink-subtle)"
        >{{ label }}</text>
      </svg>

      <div
        v-if="hover !== null"
        class="pointer-events-none absolute top-2 z-10 min-w-[9rem] rounded-lg border border-line bg-card p-2.5 shadow-pop"
        :style="tooltipSide === 'right' ? { left: '0.5rem' } : { right: '0.5rem' }"
      >
        <p class="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-subtle">
          {{ labels[hover] ?? `#${hover + 1}` }}
        </p>
        <div v-for="s in series" :key="`tt-${s.label}`" class="flex items-center justify-between gap-4 py-0.5">
          <span class="flex items-center gap-1.5 text-[12px] text-ink-muted">
            <span class="h-2 w-2 rounded-[2px]" :style="{ backgroundColor: s.color }" />
            {{ s.label }}
          </span>
          <span class="text-[12px] font-semibold text-ink tabular">
            {{ formatTooltip(s.points[hover]?.y ?? 0) }}
          </span>
        </div>
      </div>
    </div>

    <ChartLegend v-if="series.length > 1" :items="legendItems" class="mt-3 pl-[52px]" />
  </div>
</template>
