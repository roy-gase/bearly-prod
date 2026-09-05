<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "@/lib/api";
import { money0, percent, longDate, monthsToHuman, titleCase } from "@/lib/format";

import PageState from "@/components/app/PageState.vue";
import Card from "@/components/ui/Card.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Select from "@/components/ui/Select.vue";
import Badge from "@/components/ui/Badge.vue";
import Alert from "@/components/ui/Alert.vue";
import Dialog from "@/components/ui/Dialog.vue";
import Progress from "@/components/ui/Progress.vue";
import EmptyState from "@/components/ui/EmptyState.vue";

const loading = ref(true);
const error = ref("");
const goals = ref([]);
const summary = ref(null);

const GOAL_TYPES = [
  { value: "emergency_fund", label: "Emergency fund" },
  { value: "vacation", label: "Vacation" },
  { value: "house", label: "House" },
  { value: "vehicle", label: "Vehicle" },
  { value: "education", label: "Education" },
  { value: "wedding", label: "Wedding" },
  { value: "large_purchase", label: "Large purchase" },
  { value: "general", label: "General savings" },
];

const blank = () => ({
  id: null, name: "", goal_type: "general", target_amount: "",
  current_amount: "", target_date: "", monthly_contribution: "", priority: 3,
});
const form = ref(blank());
const dialogOpen = ref(false);
const saving = ref(false);
const formError = ref("");

const contribute = ref({ open: false, goal: null, amount: "" });

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [g, s] = await Promise.all([api.get("/savings/goals"), api.get("/savings/summary")]);
    goals.value = g;
    summary.value = s;
  } catch (err) {
    error.value = err.message || "Could not load your savings.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);

function openNew() {
  form.value = blank();
  formError.value = "";
  dialogOpen.value = true;
}
function openEdit(goal) {
  form.value = { ...goal, target_date: goal.target_date ?? "" };
  formError.value = "";
  dialogOpen.value = true;
}

async function save() {
  saving.value = true;
  formError.value = "";
  try {
    const body = {
      name: form.value.name,
      goal_type: form.value.goal_type,
      target_amount: Number(form.value.target_amount) || 0,
      current_amount: Number(form.value.current_amount) || 0,
      target_date: form.value.target_date || null,
      monthly_contribution: Number(form.value.monthly_contribution) || 0,
      priority: Number(form.value.priority) || 3,
    };
    if (form.value.id) await api.patch(`/savings/goals/${form.value.id}`, body);
    else await api.post("/savings/goals", body);
    dialogOpen.value = false;
    await load();
  } catch (err) {
    formError.value = err.fieldErrors?.[0]?.message || err.message || "Could not save.";
  } finally {
    saving.value = false;
  }
}

async function submitContribution() {
  await api.post(`/savings/goals/${contribute.value.goal.id}/contribute`, {
    amount: Number(contribute.value.amount),
  });
  contribute.value = { open: false, goal: null, amount: "" };
  await load();
}

async function remove(id) {
  await api.delete(`/savings/goals/${id}`);
  await load();
}

const committed = computed(() => summary.value?.monthly_committed ?? 0);
const surplus = computed(() => summary.value?.monthly_surplus ?? 0);
const overcommitted = computed(() => committed.value > surplus.value && surplus.value >= 0);
</script>

<template>
  <div>
    <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-[22px] font-semibold tracking-tight text-ink">Savings</h1>
        <p class="mt-1 text-[14px] text-ink-muted">What you are building towards, and whether you will get there.</p>
      </div>
      <Button @click="openNew">Add goal</Button>
    </div>

    <PageState :loading="loading" :error="error">
      <template v-if="summary">
        <!-- The emergency fund is treated separately: it comes before every other goal. -->
        <Card title="Emergency fund" subtitle="The foundation everything else rests on.">
          <div class="grid gap-6 sm:grid-cols-2">
            <div>
              <p class="text-[28px] font-semibold leading-none text-ink">
                {{ monthsToHuman(Math.round(summary.emergency_fund.months_covered)) }}
              </p>
              <p class="mt-1.5 text-[13px] text-ink-muted">of essential expenses covered</p>

              <div class="mt-4 space-y-3">
                <div>
                  <div class="mb-1 flex items-baseline justify-between text-[12px]">
                    <span class="text-ink">3-month target</span>
                    <span class="text-ink-muted tabular">
                      {{ money0(summary.emergency_fund.three_month.current_amount) }} /
                      {{ money0(summary.emergency_fund.three_month.target_amount) }}
                    </span>
                  </div>
                  <Progress
                    :value="summary.emergency_fund.three_month.current_amount"
                    :max="summary.emergency_fund.three_month.target_amount || 1"
                    :tone="summary.emergency_fund.three_month.is_funded ? 'good' : 'warning'"
                    label="Three month emergency fund"
                  />
                </div>
                <div>
                  <div class="mb-1 flex items-baseline justify-between text-[12px]">
                    <span class="text-ink">6-month target</span>
                    <span class="text-ink-muted tabular">
                      {{ money0(summary.emergency_fund.six_month.target_amount) }}
                    </span>
                  </div>
                  <Progress
                    :value="summary.emergency_fund.six_month.current_amount"
                    :max="summary.emergency_fund.six_month.target_amount || 1"
                    :tone="summary.emergency_fund.six_month.is_funded ? 'good' : 'primary'"
                    label="Six month emergency fund"
                  />
                </div>
              </div>
            </div>

            <div class="rounded-lg border border-line bg-page p-4">
              <p class="text-[13px] font-medium text-ink">Why this comes first</p>
              <p class="mt-1.5 text-[12.5px] leading-relaxed text-ink-muted">
                Without cash set aside, an unexpected bill becomes new debt — usually at a rate far
                higher than anything you would earn by investing the same money. Three months of
                essentials is the standard floor; six if your income varies.
              </p>
              <p v-if="!summary.emergency_fund.three_month.is_funded" class="mt-3 text-[12.5px] text-ink">
                <span class="font-semibold">{{ money0(summary.emergency_fund.three_month.shortfall) }}</span>
                left to reach three months.
              </p>
            </div>
          </div>
        </Card>

        <Alert v-if="overcommitted" variant="warning" class="mt-6" title="Your goals need more than you have spare">
          You have committed {{ money0(committed) }} a month across your goals, but only
          {{ money0(surplus) }} is left after expenses. Consider pushing a target date back rather
          than falling behind on all of them.
        </Alert>

        <div class="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Total saved</p>
            <p class="mt-1.5 text-[20px] font-semibold text-ink tabular">{{ money0(summary.total_saved) }}</p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Total target</p>
            <p class="mt-1.5 text-[20px] font-semibold text-ink tabular">{{ money0(summary.total_target) }}</p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Committed monthly</p>
            <p class="mt-1.5 text-[20px] font-semibold text-ink tabular">{{ money0(committed) }}</p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">On track</p>
            <p class="mt-1.5 text-[20px] font-semibold text-ink tabular">
              {{ summary.on_track_count }} / {{ summary.goal_count }}
            </p>
          </div>
        </div>

        <div v-if="goals.length" class="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <Card v-for="goal in goals" :key="goal.id">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="text-[15px] font-semibold text-ink">{{ goal.name }}</h3>
                  <Badge size="sm">{{ titleCase(goal.goal_type) }}</Badge>
                </div>
                <p class="mt-1 text-[12.5px] text-ink-muted">
                  {{ money0(goal.current_amount) }} of {{ money0(goal.target_amount) }}
                  <span v-if="goal.target_date"> · by {{ longDate(goal.target_date) }}</span>
                </p>
              </div>
              <Badge
                v-if="goal.progress.on_track !== null"
                :variant="goal.progress.on_track ? 'good' : 'warning'"
                size="sm"
              >{{ goal.progress.on_track ? "On track" : "Behind" }}</Badge>
            </div>

            <Progress
              class="mt-4" :value="goal.progress.progress_pct"
              :tone="goal.progress.on_track === false ? 'warning' : 'primary'"
              :label="`${goal.name} progress`"
            />
            <p class="mt-1.5 text-[12px] text-ink-muted tabular">
              {{ percent(goal.progress.progress_pct) }} complete ·
              {{ money0(goal.progress.remaining) }} to go
            </p>

            <dl class="mt-4 grid grid-cols-2 gap-3 border-t border-line pt-3 text-[12.5px]">
              <div>
                <dt class="text-ink-muted">Contributing</dt>
                <dd class="mt-0.5 font-medium text-ink tabular">{{ money0(goal.progress.current_monthly) }}/mo</dd>
              </div>
              <div v-if="goal.progress.required_monthly !== null">
                <dt class="text-ink-muted">Needed</dt>
                <dd class="mt-0.5 font-medium tabular"
                  :style="{ color: goal.progress.shortfall_monthly > 0 ? 'var(--critical-ink)' : 'var(--ink)' }">
                  {{ money0(goal.progress.required_monthly) }}/mo
                </dd>
              </div>
              <div v-else-if="goal.progress.months_at_current_rate !== null">
                <dt class="text-ink-muted">Complete in</dt>
                <dd class="mt-0.5 font-medium text-ink">{{ monthsToHuman(goal.progress.months_at_current_rate) }}</dd>
              </div>
            </dl>

            <div class="mt-4 flex gap-2">
              <Button size="sm" @click="contribute = { open: true, goal, amount: '' }">Add money</Button>
              <Button variant="secondary" size="sm" @click="openEdit(goal)">Edit</Button>
              <Button variant="ghost" size="sm" @click="remove(goal.id)">Delete</Button>
            </div>
          </Card>
        </div>

        <EmptyState
          v-else class="mt-6"
          title="No savings goals yet"
          description="Name what you are saving for and Bearly will work out what it takes each month to get there on time."
        >
          <Button @click="openNew">Add your first goal</Button>
        </EmptyState>
      </template>
    </PageState>

    <Dialog v-model:open="dialogOpen" :title="form.id ? 'Edit goal' : 'Add savings goal'">
      <form class="space-y-4" @submit.prevent="save">
        <p v-if="formError" class="text-[13px] text-[color:var(--critical-ink)]">{{ formError }}</p>
        <Input v-model="form.name" label="Goal name" required placeholder="e.g. Japan trip" />
        <Select v-model="form.goal_type" label="Type" :options="GOAL_TYPES" />
        <div class="grid gap-4 sm:grid-cols-2">
          <Input v-model="form.target_amount" label="Target amount" money required />
          <Input v-model="form.current_amount" label="Saved so far" money />
        </div>
        <div class="grid gap-4 sm:grid-cols-2">
          <Input v-model="form.target_date" label="Target date" type="date" hint="Optional" />
          <Input v-model="form.monthly_contribution" label="Monthly contribution" money />
        </div>
      </form>
      <template #footer>
        <Button variant="ghost" @click="dialogOpen = false">Cancel</Button>
        <Button :loading="saving" @click="save">{{ form.id ? "Save changes" : "Add goal" }}</Button>
      </template>
    </Dialog>

    <Dialog v-model:open="contribute.open" :title="`Add to ${contribute.goal?.name ?? ''}`" size="sm">
      <Input v-model="contribute.amount" label="Amount" money required placeholder="0.00" />
      <template #footer>
        <Button variant="ghost" @click="contribute.open = false">Cancel</Button>
        <Button :disabled="!Number(contribute.amount)" @click="submitContribution">Add money</Button>
      </template>
    </Dialog>
  </div>
</template>
