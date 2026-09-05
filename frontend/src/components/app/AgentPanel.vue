<script setup>
/**
 * One agent's recommendation.
 *
 * Always shows where the answer came from — which agent, which provider, when it
 * was generated, and the exact figures it was given — so "why is it saying this?"
 * is answerable rather than a matter of trust.
 */
import { ref } from "vue";
import { money0, relativeTime } from "@/lib/format";
import Badge from "@/components/ui/Badge.vue";
import Button from "@/components/ui/Button.vue";
import Alert from "@/components/ui/Alert.vue";

defineProps({
  agent: { type: Object, required: true },
  result: Object,
  loading: Boolean,
  error: String,
});
const emit = defineEmits(["run", "refresh"]);

const showContext = ref(false);
</script>

<template>
  <section class="rounded-xl border border-line bg-card shadow-card">
    <header class="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <h2 class="text-[15px] font-semibold text-ink">{{ agent.label }}</h2>
          <Badge v-if="agent.tier === 'planning'" variant="primary" size="sm">Deep analysis</Badge>
        </div>
        <p class="mt-1 text-[13px] leading-snug text-ink-muted">{{ agent.description }}</p>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <Button v-if="!result" size="sm" :loading="loading" :disabled="!!agent.unavailable_reason" @click="emit('run')">
          Get advice
        </Button>
        <Button v-else variant="secondary" size="sm" :loading="loading" @click="emit('refresh')">
          Refresh
        </Button>
      </div>
    </header>

    <div class="px-5 py-4">
      <Alert v-if="agent.unavailable_reason" variant="info">{{ agent.unavailable_reason }}</Alert>
      <Alert v-else-if="error" variant="critical" title="Could not generate advice">{{ error }}</Alert>

      <div v-else-if="loading && !result" class="space-y-2.5">
        <div class="h-4 w-3/4 animate-pulse rounded bg-raised" />
        <div class="h-4 w-full animate-pulse rounded bg-raised" />
        <div class="h-4 w-5/6 animate-pulse rounded bg-raised" />
      </div>

      <p v-else-if="!result" class="text-[13px] text-ink-muted">
        Nothing generated yet. Bearly only runs an agent when you ask, so opening this page costs nothing.
      </p>

      <div v-else class="space-y-5">
        <p class="text-[14px] leading-relaxed text-ink">{{ result.response.summary }}</p>

        <div v-if="result.response.recommendations.length">
          <h3 class="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">
            What to do
          </h3>
          <ol class="space-y-2.5">
            <li
              v-for="rec in result.response.recommendations" :key="rec.priority + rec.title"
              class="rounded-lg border border-line bg-page p-3.5"
            >
              <div class="flex items-start justify-between gap-3">
                <p class="text-[13.5px] font-semibold text-ink">{{ rec.title }}</p>
                <span v-if="rec.suggested_amount > 0" class="shrink-0 text-[13px] font-semibold text-primary tabular">
                  {{ money0(rec.suggested_amount) }}
                </span>
              </div>
              <p class="mt-1 text-[12.5px] leading-relaxed text-ink-muted">{{ rec.reason }}</p>
              <Badge v-if="rec.category" size="sm" class="mt-2">{{ rec.category }}</Badge>
            </li>
          </ol>
        </div>

        <div v-if="result.response.risks.length">
          <h3 class="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">
            Worth knowing
          </h3>
          <ul class="space-y-1.5">
            <li v-for="risk in result.response.risks" :key="risk" class="flex gap-2 text-[12.5px] leading-relaxed text-ink-muted">
              <svg class="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--serious)]" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 8v5m0 3h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
              </svg>
              <span>{{ risk }}</span>
            </li>
          </ul>
        </div>

        <div v-if="result.response.next_steps.length">
          <h3 class="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">Next steps</h3>
          <ul class="space-y-1.5">
            <li v-for="step in result.response.next_steps" :key="step" class="flex gap-2 text-[12.5px] leading-relaxed text-ink-muted">
              <svg class="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="m5 12 4.5 4.5L19 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <span>{{ step }}</span>
            </li>
          </ul>
        </div>

        <!-- Provenance. The user can always see what the agent was actually given. -->
        <div class="border-t border-line pt-3">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-subtle">
            <span>{{ result.cached ? "Saved answer" : "Generated" }} {{ relativeTime(result.generated_at) }}</span>
            <span aria-hidden="true">·</span>
            <span v-if="result.provider === 'stub'">Calculated by Bearly, no AI call</span>
            <span v-else-if="result.provider === 'none'">No analysis needed</span>
            <span v-else>{{ result.model }} via {{ result.provider }}</span>
            <button
              v-if="Object.keys(result.context_sent || {}).length"
              type="button" class="underline underline-offset-2 hover:text-ink-muted"
              @click="showContext = !showContext"
            >{{ showContext ? "Hide" : "Show" }} the figures used</button>
          </div>

          <pre
            v-if="showContext"
            class="mt-2 max-h-64 overflow-auto rounded-lg border border-line bg-page p-3 text-[11px] leading-relaxed text-ink-muted"
          >{{ JSON.stringify(result.context_sent, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </section>
</template>
