<script setup>
/** A small trend mark for stat tiles. No axes — the tile's value carries the number. */
import { computed } from "vue";

const props = defineProps({
  values: { type: Array, default: () => [] },
  color: { type: String, default: "var(--primary)" },
  width: { type: Number, default: 96 },
  height: { type: Number, default: 28 },
});

const path = computed(() => {
  const vals = props.values.map(Number).filter((n) => Number.isFinite(n));
  if (vals.length < 2) return "";
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const step = props.width / (vals.length - 1);
  return vals
    .map((v, i) => {
      const x = i * step;
      const y = props.height - 3 - ((v - min) / span) * (props.height - 6);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
});
</script>

<template>
  <svg v-if="path" :viewBox="`0 0 ${width} ${height}`" :width="width" :height="height" aria-hidden="true" class="overflow-visible">
    <path :d="path" fill="none" :stroke="color" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
</template>
