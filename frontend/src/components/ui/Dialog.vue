<script setup>
import { onBeforeUnmount, onMounted, ref, watch, nextTick } from "vue";

const props = defineProps({
  open: Boolean,
  title: String,
  description: String,
  size: { type: String, default: "md" }, // sm | md | lg
});
const emit = defineEmits(["update:open"]);

const panel = ref(null);

function close() {
  emit("update:open", false);
}

function onKeydown(event) {
  if (!props.open) return;
  if (event.key === "Escape") {
    close();
    return;
  }
  // Keep focus inside the dialog while it is open.
  if (event.key === "Tab" && panel.value) {
    const focusable = panel.value.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
}

watch(
  () => props.open,
  async (isOpen) => {
    document.body.style.overflow = isOpen ? "hidden" : "";
    if (isOpen) {
      await nextTick();
      panel.value?.querySelector("input, select, textarea, button")?.focus();
    }
  },
);

onMounted(() => document.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown);
  document.body.style.overflow = "";
});

const WIDTHS = { sm: "max-w-sm", md: "max-w-lg", lg: "max-w-2xl" };
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <div class="absolute inset-0 bg-[color:var(--ink)]/40 backdrop-blur-[2px]" @click="close" />
      <div
        ref="panel"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        class="relative z-10 max-h-[92vh] w-full overflow-y-auto rounded-t-2xl border border-line bg-card shadow-pop animate-fade-in sm:rounded-2xl"
        :class="WIDTHS[size] ?? WIDTHS.md"
      >
        <header v-if="title" class="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <h2 class="text-base font-semibold text-ink">{{ title }}</h2>
            <p v-if="description" class="mt-1 text-[13px] text-ink-muted">{{ description }}</p>
          </div>
          <button
            type="button"
            class="-mr-1 -mt-1 rounded-md p-1.5 text-ink-subtle transition hover:bg-raised hover:text-ink"
            aria-label="Close"
            @click="close"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="m5 5 10 10M15 5 5 15" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
            </svg>
          </button>
        </header>
        <div class="px-5 py-4"><slot /></div>
        <footer v-if="$slots.footer" class="flex justify-end gap-2 border-t border-line px-5 py-4">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>
