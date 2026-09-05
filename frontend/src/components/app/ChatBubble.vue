<script setup>
/**
 * One chat turn.
 *
 * Assistant turns show which deterministic functions ran, so a figure can always
 * be traced back to Bearly's engine rather than taken on trust.
 */
import { computed } from "vue";
import BearAvatar from "@/components/brand/BearAvatar.vue";

const props = defineProps({
  role: { type: String, required: true },
  content: { type: String, default: "" },
  toolCalls: { type: Array, default: () => [] },
  streaming: Boolean,
});

const isUser = computed(() => props.role === "user");

// Light formatting: paragraphs, and **bold** which the model tends to emit.
const paragraphs = computed(() =>
  (props.content || "")
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean),
);

function inline(text) {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br />");
}
</script>

<template>
  <div class="flex gap-3" :class="isUser ? 'justify-end' : ''">
    <BearAvatar
      v-if="!isUser"
      class="mt-0.5"
      :size="28"
      detail="reduced"
      :inverted="streaming && !paragraphs.length"
    />

    <div :class="isUser ? 'max-w-[85%]' : 'min-w-0 flex-1'">
      <!-- What ran, before the answer, so the provenance reads first -->
      <ul v-if="!isUser && toolCalls.length" class="mb-2 flex flex-wrap gap-1.5">
        <li
          v-for="(tool, i) in toolCalls" :key="`${tool.name}-${i}`"
          class="inline-flex items-center gap-1.5 rounded-md bg-raised px-2 py-1 text-[11px] text-ink-muted"
        >
          <svg class="h-3 w-3 shrink-0 text-primary" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" stroke="currentColor" stroke-width="1.8" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6h.09A1.65 1.65 0 0 0 10.6 3.09V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9v.09a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" stroke="currentColor" stroke-width="1.4" />
          </svg>
          {{ tool.label || tool.name }}
        </li>
      </ul>

      <div
        :class="isUser
          ? 'rounded-2xl rounded-br-md bg-[color:var(--primary-soft)] px-4 py-2.5'
          : streaming && !paragraphs.length
            ? 'rounded-[14px] rounded-bl-[4px] bg-[color:var(--bubble)] px-3.5 py-3'
            : 'rounded-2xl rounded-bl-md border border-line bg-card px-4 py-3'"
      >
        <p
          v-for="(block, i) in paragraphs" :key="i"
          class="text-[14px] leading-relaxed text-ink"
          :class="i > 0 ? 'mt-3' : ''"
          v-html="inline(block)"
        />
        <span
          v-if="streaming && !paragraphs.length"
          class="flex items-center gap-1.5 py-1"
          aria-label="Thinking"
        >
          <span
            v-for="d in 3" :key="d"
            class="h-1.5 w-1.5 rounded-full bg-[color:var(--fur)] [animation:bl-dot_1.1s_ease-in-out_infinite]"
            :style="{ animationDelay: `${(d - 1) * 180}ms` }"
          />
        </span>
        <span
          v-else-if="streaming"
          class="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-pulse bg-primary"
          aria-hidden="true"
        />
      </div>
    </div>
  </div>
</template>
