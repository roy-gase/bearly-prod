<script setup>
/** Loading and error states, so no page ever renders half-truthful numbers. */
import Alert from "@/components/ui/Alert.vue";

defineProps({ loading: Boolean, error: String, rows: { type: Number, default: 3 } });
</script>

<template>
  <div v-if="loading" class="space-y-3">
    <div v-for="i in rows" :key="i" class="h-24 animate-pulse rounded-xl bg-raised" />
  </div>
  <Alert v-else-if="error" variant="critical" title="Something went wrong">{{ error }}</Alert>
  <slot v-else />
</template>
