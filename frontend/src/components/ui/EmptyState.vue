<script setup>
import BearAvatar from "@/components/brand/BearAvatar.vue";

defineProps({
  title: { type: String, required: true },
  description: String,
});
</script>

<template>
  <div class="flex flex-col items-center justify-center rounded-lg border border-dashed border-line px-6 py-10 text-center">
    <BearAvatar :size="56" class="mb-3" />
    <p class="text-sm font-semibold text-ink">{{ title }}</p>
    <p v-if="description" class="mt-1 max-w-sm text-[13px] leading-relaxed text-ink-muted">{{ description }}</p>
    <div v-if="$slots.default" class="mt-4"><slot /></div>
  </div>
</template>
