<script setup>
import { onMounted, ref } from "vue";

const KEY = "bearly.theme";
const theme = ref("system");

function apply(value) {
  const root = document.documentElement;
  if (value === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", value);
}

function cycle() {
  theme.value = { system: "light", light: "dark", dark: "system" }[theme.value];
  apply(theme.value);
  try {
    localStorage.setItem(KEY, theme.value);
  } catch {
    /* private browsing — the choice just will not persist */
  }
}

onMounted(() => {
  try {
    theme.value = localStorage.getItem(KEY) || "system";
  } catch {
    theme.value = "system";
  }
  apply(theme.value);
});

const ICONS = {
  system: "M4 5h16v11H4zM9 20h6M12 16v4",
  light: "M12 4v2m0 12v2M4 12H2m20 0h-2M6 6 4.5 4.5M18 6l1.5-1.5M6 18l-1.5 1.5M18 18l1.5 1.5M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z",
  dark: "M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z",
};
const LABELS = { system: "Match system theme", light: "Light theme", dark: "Dark theme" };
</script>

<template>
  <button
    type="button"
    class="rounded-lg p-2 text-ink-muted transition hover:bg-raised hover:text-ink"
    :aria-label="LABELS[theme]"
    :title="LABELS[theme]"
    @click="cycle"
  >
    <svg class="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path :d="ICONS[theme]" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </button>
</template>
