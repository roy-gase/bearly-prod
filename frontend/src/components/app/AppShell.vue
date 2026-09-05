<script setup>
import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import ThemeToggle from "./ThemeToggle.vue";
import BearLockup from "@/components/brand/BearLockup.vue";
import BearMark from "@/components/brand/BearMark.vue";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const mobileOpen = ref(false);

const NAV = [
  { name: "dashboard", label: "Dashboard", icon: "M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6v-9h-6v9Zm0-16v5h6V4h-6Z" },
  { name: "budget", label: "Budget", icon: "M4 6h16M4 12h16M4 18h10" },
  { name: "expenses", label: "Expenses", icon: "M3 7h18v12H3zM3 11h18M7 15h4" },
  { name: "debt", label: "Debt", icon: "M3 17V9m5 8V5m5 12v-6m5 6V7" },
  { name: "savings", label: "Savings", icon: "M12 3v18m5-15H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" },
  { name: "investments", label: "Investments", icon: "m3 17 5-5 4 4 8-8M16 8h5v5" },
  { name: "coach", label: "Bearly AI", mark: true },
];

const current = computed(() => route.name);

async function signOut() {
  await auth.logout();
  router.push({ name: "login" });
}
</script>

<template>
  <div class="min-h-dvh bg-page">
    <!-- Desktop sidebar -->
    <aside class="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-line bg-card lg:flex">
      <div class="flex h-16 items-center px-5">
        <BearLockup :to="{ name: 'dashboard' }" :mark-size="28" word-size="17px" />
      </div>

      <nav class="flex-1 space-y-0.5 px-3 py-2" aria-label="Main">
        <RouterLink
          v-for="item in NAV" :key="item.name" :to="{ name: item.name }"
          :class="[
            'flex items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] font-medium transition',
            current === item.name ? 'bg-[color:var(--primary-soft)] text-primary' : 'text-ink-muted hover:bg-raised hover:text-ink',
          ]"
          :aria-current="current === item.name ? 'page' : undefined"
        >
          <BearMark v-if="item.mark" :size="18" aria-hidden="true" />
          <svg v-else class="h-[18px] w-[18px] shrink-0" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path :d="item.icon" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="border-t border-line p-3">
        <RouterLink
          :to="{ name: 'settings' }"
          class="flex items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] text-ink-muted transition hover:bg-raised hover:text-ink"
        >
          <span class="flex h-7 w-7 items-center justify-center rounded-full bg-[color:var(--primary-soft)] text-[12px] font-semibold text-primary">
            {{ auth.displayName.charAt(0).toUpperCase() }}
          </span>
          <span class="min-w-0 truncate">{{ auth.displayName }}</span>
        </RouterLink>
      </div>
    </aside>

    <!-- Mobile header -->
    <header class="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-card px-4 lg:hidden">
      <BearLockup :to="{ name: 'dashboard' }" :mark-size="22" word-size="15px" />
      <button
        type="button" class="rounded-md p-2 text-ink-muted hover:bg-raised"
        :aria-expanded="mobileOpen" aria-label="Menu"
        @click="mobileOpen = !mobileOpen"
      >
        <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path :d="mobileOpen ? 'M6 6l12 12M18 6 6 18' : 'M4 7h16M4 12h16M4 17h16'"
            stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
        </svg>
      </button>
    </header>

    <div v-if="mobileOpen" class="fixed inset-x-0 top-14 z-30 border-b border-line bg-card p-3 shadow-pop lg:hidden">
      <RouterLink
        v-for="item in NAV" :key="item.name" :to="{ name: item.name }"
        class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium"
        :class="current === item.name ? 'bg-[color:var(--primary-soft)] text-primary' : 'text-ink-muted'"
        @click="mobileOpen = false"
      >
        <BearMark v-if="item.mark" :size="18" aria-hidden="true" />
        <svg v-else class="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path :d="item.icon" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        {{ item.label }}
      </RouterLink>
      <RouterLink
        :to="{ name: 'settings' }" class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-ink-muted"
        @click="mobileOpen = false"
      >Settings</RouterLink>
    </div>

    <!-- Content -->
    <div class="lg:pl-60">
      <div class="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div class="mb-6 flex items-start justify-between gap-4">
          <div class="min-w-0">
            <slot name="heading">
              <h1 class="text-[22px] font-semibold tracking-tight text-ink">{{ $route.meta.title }}</h1>
            </slot>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <slot name="actions" />
            <ThemeToggle />
            <button
              type="button"
              class="hidden rounded-lg px-3 py-2 text-[13px] text-ink-muted transition hover:bg-raised hover:text-ink lg:block"
              @click="signOut"
            >Sign out</button>
          </div>
        </div>
        <slot />
      </div>
    </div>
  </div>
</template>
