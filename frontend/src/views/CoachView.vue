<script setup>
/**
 * The Bearly coach — a conversation.
 *
 * The specialists still exist: the agent calls them as tools when a question
 * warrants a full analysis. What the user sees is one chat.
 */
import { computed, nextTick, onMounted, ref } from "vue";
import { api } from "@/lib/api";
import { streamMessage } from "@/lib/chat";
import { useAuthStore } from "@/stores/auth";
import { relativeTime } from "@/lib/format";

import ChatBubble from "@/components/app/ChatBubble.vue";
import Button from "@/components/ui/Button.vue";
import Alert from "@/components/ui/Alert.vue";
import BearAvatarLive from "@/components/brand/BearAvatarLive.vue";

const auth = useAuthStore();

const conversations = ref([]);
const activeId = ref(null);
const messages = ref([]);
const starters = ref([]);
const provider = ref("stub");

const draft = ref("");
const sending = ref(false);
const loading = ref(true);
const error = ref("");
const scroller = ref(null);
const composer = ref(null);
const composerFocused = ref(false);
const showHistory = ref(false);

// The streaming assistant turn, held separately until it is committed.
const pending = ref(null);

async function scrollToBottom() {
  await nextTick();
  if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [meta, list] = await Promise.all([
      api.get("/ai/chat/starters"),
      api.get("/ai/chat/conversations"),
    ]);
    starters.value = meta.starters;
    provider.value = meta.provider;
    conversations.value = list;
    if (list.length) await openConversation(list[0].id);
    else await newConversation();
  } catch (err) {
    error.value = err.message || "Could not load the coach.";
  } finally {
    loading.value = false;
  }
}

async function openConversation(id) {
  const detail = await api.get(`/ai/chat/conversations/${id}`);
  activeId.value = detail.id;
  messages.value = detail.messages;
  pending.value = null;
  showHistory.value = false;
  await scrollToBottom();
}

async function newConversation() {
  const convo = await api.post("/ai/chat/conversations");
  conversations.value = [convo, ...conversations.value];
  activeId.value = convo.id;
  messages.value = [];
  pending.value = null;
  showHistory.value = false;
  composer.value?.focus();
}

async function removeConversation(id) {
  await api.delete(`/ai/chat/conversations/${id}`);
  conversations.value = conversations.value.filter((c) => c.id !== id);
  if (activeId.value === id) {
    if (conversations.value.length) await openConversation(conversations.value[0].id);
    else await newConversation();
  }
}

async function send(text) {
  const content = (text ?? draft.value).trim();
  if (!content || sending.value) return;

  draft.value = "";
  sending.value = true;
  error.value = "";
  messages.value.push({ id: `local-${Date.now()}`, role: "user", content, tool_calls: [] });
  pending.value = { role: "assistant", content: "", tool_calls: [] };
  await scrollToBottom();

  try {
    await streamMessage({
      conversationId: activeId.value,
      content,
      onEvent: (event) => {
        if (event.type === "text") {
          pending.value.content += event.delta;
          scrollToBottom();
        } else if (event.type === "tool") {
          pending.value.tool_calls.push({ name: event.name, label: event.label });
          scrollToBottom();
        } else if (event.type === "notice") {
          error.value = event.message;
        } else if (event.type === "error") {
          error.value = event.message;
        } else if (event.type === "done") {
          messages.value.push({
            id: event.message_id,
            role: "assistant",
            content: pending.value.content,
            tool_calls: event.tools_used ?? pending.value.tool_calls,
          });
          pending.value = null;
        }
      },
    });
    // Refresh the sidebar so the auto-generated title appears.
    conversations.value = await api.get("/ai/chat/conversations");
  } catch (err) {
    error.value = err.message || "Could not send that message.";
  } finally {
    if (pending.value) {
      // Stream ended without a done event — keep whatever text arrived.
      if (pending.value.content.trim()) messages.value.push({ ...pending.value, id: `local-a-${Date.now()}` });
      pending.value = null;
    }
    sending.value = false;
    await scrollToBottom();
    composer.value?.focus();
  }
}

function onKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    send();
  }
}

onMounted(load);

const isEmpty = computed(() => messages.value.length === 0 && !pending.value);

const avatarState = computed(() => {
  if (sending.value) return "thinking";
  if (composerFocused.value) return "listening";
  return "idle";
});
</script>

<template>
  <div class="flex flex-col" style="height: calc(100dvh - 8rem)">
    <!-- Header -->
    <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h1 class="text-[22px] font-semibold tracking-tight text-ink">Bearly AI</h1>
        <p class="mt-1 text-[13.5px] text-ink-muted">
          Ask anything about your money. Every number comes from your own figures.
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <Button variant="secondary" size="sm" @click="showHistory = !showHistory">
          History<span v-if="conversations.length" class="ml-1 text-ink-subtle">{{ conversations.length }}</span>
        </Button>
        <Button size="sm" @click="newConversation">New chat</Button>
      </div>
    </div>

    <!-- Conversation history -->
    <div v-if="showHistory" class="mb-4 rounded-xl border border-line bg-card p-2">
      <p v-if="!conversations.length" class="px-2 py-3 text-[13px] text-ink-muted">No conversations yet.</p>
      <ul v-else class="max-h-56 overflow-y-auto">
        <li v-for="c in conversations" :key="c.id">
          <div
            class="flex items-center gap-2 rounded-lg px-2 py-2 transition hover:bg-raised"
            :class="c.id === activeId ? 'bg-raised' : ''"
          >
            <button type="button" class="min-w-0 flex-1 text-left" @click="openConversation(c.id)">
              <span class="block truncate text-[13px] text-ink">{{ c.title }}</span>
              <span class="block text-[11px] text-ink-subtle">{{ relativeTime(c.last_message_at || c.created_at) }}</span>
            </button>
            <button
              type="button" class="rounded p-1 text-ink-subtle hover:text-[color:var(--critical-ink)]"
              aria-label="Delete conversation" @click="removeConversation(c.id)"
            >
              <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                <path d="M5 7h14M9 7V5h6v2m-8 0 1 13h8l1-13" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </div>
        </li>
      </ul>
    </div>

    <!-- Messages -->
    <div ref="scroller" class="min-h-0 flex-1 overflow-y-auto rounded-xl border border-line bg-page p-4 sm:p-5">
      <div v-if="loading" class="space-y-3">
        <div v-for="i in 3" :key="i" class="h-16 animate-pulse rounded-xl bg-raised" />
      </div>

      <!-- Opening state: who I am, and what to ask -->
      <div v-else-if="isEmpty" class="flex h-full flex-col items-center justify-center py-6 text-center">
        <BearAvatarLive :size="112" state="idle" />
        <h2 class="mt-3 text-[17px] font-semibold text-ink">
          Hi {{ auth.displayName }} — where do you want to start?
        </h2>
        <p class="mt-1.5 max-w-md text-[13.5px] leading-relaxed text-ink-muted">
          I read your real balances, budget and debts before I answer, and I run Bearly's
          calculations rather than guessing at the maths.
        </p>
        <div class="mt-5 flex flex-wrap justify-center gap-2">
          <button
            v-for="s in starters" :key="s.label" type="button"
            class="rounded-full border border-line bg-card px-3.5 py-2 text-[13px] text-ink transition hover:border-line-strong hover:bg-raised"
            @click="send(s.prompt)"
          >{{ s.label }}</button>
        </div>
      </div>

      <div v-else class="space-y-5">
        <ChatBubble
          v-for="m in messages" :key="m.id"
          :role="m.role" :content="m.content" :tool-calls="m.tool_calls"
        />
        <ChatBubble
          v-if="pending"
          role="assistant" :content="pending.content" :tool-calls="pending.tool_calls" streaming
        />
      </div>
    </div>

    <Alert v-if="error" variant="warning" class="mt-3">{{ error }}</Alert>

    <!-- Composer -->
    <div class="mt-3">
      <div
        class="flex items-end gap-3 rounded-full border px-2.5 py-2 pr-2 focus-within:border-[color:var(--ear)]"
        :style="{ background: 'var(--composer)', borderColor: 'var(--composer-line)' }"
      >
        <BearAvatarLive :size="40" composer :state="avatarState" class="mb-0.5" />
        <textarea
          ref="composer"
          v-model="draft"
          rows="1"
          placeholder="Ask Bearly where your money went…"
          maxlength="2000"
          class="max-h-32 min-h-[2.5rem] flex-1 resize-none bg-transparent py-2 text-[14px] text-ink outline-none placeholder:text-ink-muted"
          :disabled="sending"
          @focus="composerFocused = true"
          @blur="composerFocused = false"
          @keydown="onKeydown"
          @input="(e) => { e.target.style.height = 'auto'; e.target.style.height = `${Math.min(e.target.scrollHeight, 128)}px`; }"
        />
        <Button size="icon" :loading="sending" :disabled="!draft.trim()" aria-label="Send" @click="send()">
          <svg v-if="!sending" class="h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </Button>
      </div>

      <p class="mt-2 px-1 text-[11px] leading-relaxed text-ink-subtle">
        <template v-if="provider === 'stub'">
          Running on Bearly's own calculations — no AI credentials configured, nothing billed.
        </template>
        <template v-else>
          Bearly runs your real figures through its finance engine before answering.
        </template>
        Educational guidance, not licensed financial advice.
      </p>
    </div>
  </div>
</template>
