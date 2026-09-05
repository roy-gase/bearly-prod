<script setup>
/**
 * Part-to-whole as a single 100% stacked bar with a labelled legend.
 *
 * Chosen over a pie or donut deliberately: angle is harder to compare than
 * length, and the legend carries the exact percentages either way. Segments are
 * separated by a 2px surface gap so adjacent fills never bleed together.
 */
import { computed, ref } from "vue";
import { money0, percent } from "@/lib/format";

const props = defineProps({
  /** [{ label, value, color }] — already folded to at most six slices. */
  slices: { type: Array, default: () => [] },
  height: { type: Number, default: 14 },
  showTable: { type: Boolean, default: true },
});

const hover = ref(null);
const total = computed(() => props.slices.reduce((sum, s) => sum + Number(s.value || 0), 0));

const segments = computed(() => {
  if (!total.value) return [];
  let offset = 0;
  return props.slices.map((slice, index) => {
    const pct = (Number(slice.value) / total.value) * 100;
    const seg = { ...slice, pct, offset, index };
    offset += pct;
    return seg;
  });
});
</script>

<template>
  <div class="w-full">
    <div
      class="flex w-full overflow-hidden rounded-full bg-raised"
      :style="{ height: `${height}px`, gap: '2px' }"
      role="img"
      :aria-label="`Allocation across ${slices.length} categories`"
    >
      <div
        v-for="seg in segments"
        :key="seg.label"
        class="h-full transition-opacity first:rounded-l-full last:rounded-r-full"
        :style="{
          width: `${seg.pct}%`,
          backgroundColor: seg.color,
          opacity: hover === null || hover === seg.index ? 1 : 0.4,
        }"
        @mouseenter="hover = seg.index"
        @mouseleave="hover = null"
      />
    </div>

    <!-- The legend doubles as the table view: every slice is labelled with its
         own value, so no colour has to be decoded on its own. -->
    <ul v-if="showTable" class="mt-3 space-y-1.5">
      <li
        v-for="seg in segments"
        :key="seg.label"
        class="flex items-center justify-between gap-3 rounded-md px-1 py-0.5 transition-colors"
        :class="hover === seg.index ? 'bg-raised' : ''"
        @mouseenter="hover = seg.index"
        @mouseleave="hover = null"
      >
        <span class="flex min-w-0 items-center gap-2">
          <span class="h-2.5 w-2.5 shrink-0 rounded-[3px]" :style="{ backgroundColor: seg.color }" />
          <span class="truncate text-[13px] text-ink">{{ seg.label }}</span>
        </span>
        <span class="flex shrink-0 items-baseline gap-2">
          <span class="text-[13px] font-medium text-ink tabular">{{ money0(seg.value) }}</span>
          <span class="w-10 text-right text-[12px] text-ink-muted tabular">{{ percent(seg.pct) }}</span>
        </span>
      </li>
    </ul>
  </div>
</template>
