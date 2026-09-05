<script setup>
/**
 * A legend is present whenever two or more series share a plot, so identity is
 * never carried by colour alone.
 */
defineProps({
  /** [{ label, color, value? }] */
  items: { type: Array, default: () => [] },
});
</script>

<template>
  <ul class="flex flex-wrap items-center gap-x-4 gap-y-1.5">
    <li v-for="item in items" :key="item.label" class="flex items-center gap-1.5">
      <span
        class="h-2.5 w-2.5 shrink-0 rounded-[3px]"
        :style="{ backgroundColor: item.color }"
        aria-hidden="true"
      />
      <span class="text-[12px] text-ink-muted">{{ item.label }}</span>
      <span v-if="item.value != null" class="text-[12px] font-medium text-ink tabular">{{ item.value }}</span>
    </li>
  </ul>
</template>
