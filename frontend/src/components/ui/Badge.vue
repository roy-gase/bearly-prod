<script setup>
import { computed } from "vue";

const props = defineProps({
  variant: { type: String, default: "neutral" }, // neutral | good | warning | serious | critical | primary
  size: { type: String, default: "md" },
});

const VARIANTS = {
  neutral: "bg-raised text-ink-muted",
  primary: "bg-[color:var(--primary-soft)] text-primary",
  good: "bg-[color:var(--primary-soft)] text-[color:var(--good-ink)]",
  warning: "bg-[color:var(--warning)]/15 text-ink",
  serious: "bg-[color:var(--serious)]/18 text-ink",
  critical: "bg-[color:var(--critical)]/12 text-[color:var(--critical-ink)]",
};

const classes = computed(() => [
  "inline-flex items-center gap-1 rounded-md font-medium whitespace-nowrap",
  props.size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-0.5 text-[12px]",
  VARIANTS[props.variant] ?? VARIANTS.neutral,
]);
</script>

<template>
  <span :class="classes"><slot /></span>
</template>
