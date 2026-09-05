<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import AppShell from "@/components/app/AppShell.vue";
import BearMark from "@/components/brand/BearMark.vue";

const route = useRoute();
const auth = useAuthStore();

// Auth screens and onboarding render without the app chrome.
const bare = computed(() => route.meta.layout === "auth" || route.meta.layout === "bare");
</script>

<template>
  <div v-if="!auth.ready" class="flex min-h-dvh items-center justify-center bg-page">
    <div class="flex flex-col items-center gap-3">
      <BearMark :size="40" variant="icon" />
      <span class="text-[13px] text-ink-muted">Loading Bearly…</span>
    </div>
  </div>

  <RouterView v-else-if="bare" />

  <AppShell v-else>
    <RouterView />
  </AppShell>
</template>
