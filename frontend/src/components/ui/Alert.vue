<script setup>
import { computed } from "vue";

const props = defineProps({
  variant: { type: String, default: "info" }, // info | good | warning | critical
  title: String,
});

const CONFIG = {
  info: { ring: "border-line", bg: "bg-raised", icon: "M12 9v4m0 4h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z", tint: "text-ink-muted" },
  good: { ring: "border-[color:var(--good)]/35", bg: "bg-[color:var(--primary-soft)]", icon: "m5 12 4.5 4.5L19 7", tint: "text-[color:var(--good-ink)]" },
  warning: { ring: "border-[color:var(--warning)]/45", bg: "bg-[color:var(--warning)]/10", icon: "M12 8v5m0 3h.01M10.3 3.9 2.6 17.4A2 2 0 0 0 4.3 20.4h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z", tint: "text-ink" },
  critical: { ring: "border-[color:var(--critical)]/40", bg: "bg-[color:var(--critical)]/8", icon: "M12 8v5m0 3h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z", tint: "text-[color:var(--critical-ink)]" },
};
const config = computed(() => CONFIG[props.variant] ?? CONFIG.info);
</script>

<template>
  <!-- Icon plus text: the colour is never the only carrier of meaning. -->
  <div class="flex gap-3 rounded-lg border px-4 py-3" :class="[config.ring, config.bg]" role="status">
    <svg class="mt-0.5 h-4 w-4 shrink-0" :class="config.tint" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path :d="config.icon" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
    <div class="min-w-0 text-[13px] leading-relaxed">
      <p v-if="title" class="font-semibold text-ink">{{ title }}</p>
      <div :class="title ? 'mt-0.5 text-ink-muted' : 'text-ink'"><slot /></div>
    </div>
  </div>
</template>
