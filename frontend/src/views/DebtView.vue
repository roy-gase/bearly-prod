<script setup>
/**
 * Debt payoff. Every projection on this page is computed by the backend's
 * amortisation engine — the comparison is arithmetic, not opinion.
 */
import { computed, onMounted, ref, watch } from "vue";
import { api } from "@/lib/api";
import { money0, percent, monthsToHuman, titleCase } from "@/lib/format";

import PageState from "@/components/app/PageState.vue";
import Card from "@/components/ui/Card.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Select from "@/components/ui/Select.vue";
import Badge from "@/components/ui/Badge.vue";
import Alert from "@/components/ui/Alert.vue";
import Dialog from "@/components/ui/Dialog.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import LineChart from "@/components/charts/LineChart.vue";

const loading = ref(true);
const error = ref("");
const debts = ref([]);
const payoff = ref(null);
const extra = ref("");
const strategy = ref("avalanche");

const blank = () => ({
  id: null, name: "", debt_type: "credit_card", current_balance: "",
  apr: "", minimum_payment: "", due_day: "",
});
const form = ref(blank());
const dialogOpen = ref(false);
const saving = ref(false);
const formError = ref("");

const DEBT_TYPES = [
  { value: "credit_card", label: "Credit card" },
  { value: "auto_loan", label: "Auto loan" },
  { value: "student_loan", label: "Student loan" },
  { value: "personal_loan", label: "Personal loan" },
  { value: "mortgage", label: "Mortgage" },
  { value: "medical", label: "Medical" },
  { value: "other", label: "Other" },
];

async function load() {
  loading.value = true;
  error.value = "";
  try {
    debts.value = await api.get("/debts");
    if (debts.value.length) await recalc();
  } catch (err) {
    error.value = err.message || "Could not load your debts.";
  } finally {
    loading.value = false;
  }
}

async function recalc() {
  payoff.value = await api.post("/debts/payoff", { extra_monthly: Number(extra.value) || 0 });
  if (extra.value === "" && payoff.value.suggested_extra_from_cash_flow > 0) {
    extra.value = String(Math.round(payoff.value.suggested_extra_from_cash_flow));
  }
}

let debounce;
watch(extra, () => {
  clearTimeout(debounce);
  debounce = setTimeout(() => debts.value.length && recalc(), 300);
});

onMounted(load);

function openNew() {
  form.value = blank();
  formError.value = "";
  dialogOpen.value = true;
}
function openEdit(debt) {
  form.value = { ...debt, due_day: debt.due_day ?? "" };
  formError.value = "";
  dialogOpen.value = true;
}

async function save() {
  saving.value = true;
  formError.value = "";
  try {
    const body = {
      name: form.value.name,
      debt_type: form.value.debt_type,
      current_balance: Number(form.value.current_balance) || 0,
      apr: Number(form.value.apr) || 0,
      minimum_payment: Number(form.value.minimum_payment) || 0,
      due_day: form.value.due_day ? Number(form.value.due_day) : null,
    };
    if (form.value.id) await api.patch(`/debts/${form.value.id}`, body);
    else await api.post("/debts", body);
    dialogOpen.value = false;
    await load();
  } catch (err) {
    formError.value = err.fieldErrors?.[0]?.message || err.message || "Could not save.";
  } finally {
    saving.value = false;
  }
}

async function remove(id) {
  await api.delete(`/debts/${id}`);
  await load();
}

const chosen = computed(() => (payoff.value ? payoff.value[strategy.value] : null));
const other = computed(() => (payoff.value ? payoff.value[strategy.value === "avalanche" ? "snowball" : "avalanche"] : null));

const timelineSeries = computed(() => {
  if (!payoff.value) return [];
  const build = (key, color, label) => ({
    label,
    color,
    points: payoff.value[key].balance_timeline.map((p) => ({ x: p.month, y: p.balance })),
  });
  return [
    build("avalanche", "var(--series-1)", "Avalanche"),
    build("snowball", "var(--series-2)", "Snowball"),
    build("minimum_only", "var(--series-4)", "Minimums only"),
  ];
});

const timelineLabels = computed(() => {
  if (!payoff.value) return [];
  return payoff.value.minimum_only.balance_timeline.map((p) =>
    p.month % 12 === 0 ? `${p.month / 12}y` : "",
  );
});

const ordered = computed(() => {
  if (!chosen.value) return [];
  return chosen.value.per_debt;
});
</script>

<template>
  <div>
    <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-[22px] font-semibold tracking-tight text-ink">Debt</h1>
        <p class="mt-1 text-[14px] text-ink-muted">What you owe, and the fastest way out.</p>
      </div>
      <Button @click="openNew">Add debt</Button>
    </div>

    <PageState :loading="loading" :error="error">
      <template v-if="debts.length && payoff">
        <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Total owed</p>
            <p class="mt-1.5 text-[22px] font-semibold text-ink tabular">{{ money0(payoff.summary.total_debt) }}</p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Minimum payments</p>
            <p class="mt-1.5 text-[22px] font-semibold text-ink tabular">{{ money0(payoff.summary.monthly_minimum_payments) }}</p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Average rate</p>
            <p class="mt-1.5 text-[22px] font-semibold text-ink tabular">{{ percent(payoff.summary.weighted_average_apr, 1) }}</p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Debt-free in</p>
            <p class="mt-1.5 text-[22px] font-semibold text-ink">
              {{ chosen?.months_to_debt_free ? monthsToHuman(chosen.months_to_debt_free) : "—" }}
            </p>
          </div>
        </div>

        <Alert v-if="chosen && !chosen.payable" variant="critical" class="mt-6" title="These payments will not clear the balance">
          {{ chosen.note }}
        </Alert>

        <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card class="lg:col-span-2" title="Compare payoff strategies"
            subtitle="Both plans are simulated month by month by Bearly, using your actual balances and rates.">
            <div class="mb-5 max-w-xs">
              <Input v-model="extra" label="Extra payment each month" money
                hint="On top of your minimums. Try different amounts to see the effect." />
            </div>

            <div class="grid gap-3 sm:grid-cols-2">
              <button
                v-for="key in ['avalanche', 'snowball']" :key="key" type="button"
                :aria-pressed="strategy === key"
                :class="[
                  'rounded-lg border p-4 text-left transition',
                  strategy === key ? 'border-primary bg-[color:var(--primary-soft)]' : 'border-line hover:border-line-strong',
                ]"
                @click="strategy = key"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="text-[13.5px] font-semibold text-ink">
                    {{ key === "avalanche" ? "Avalanche" : "Snowball" }}
                  </span>
                  <Badge v-if="payoff.lower_interest_strategy === key" variant="good" size="sm">Cheaper</Badge>
                </div>
                <p class="mt-1 text-[12px] leading-snug text-ink-muted">
                  {{ key === "avalanche" ? "Highest interest rate first" : "Smallest balance first" }}
                </p>
                <dl class="mt-3 space-y-1 text-[12.5px]">
                  <div class="flex justify-between">
                    <dt class="text-ink-muted">Debt-free in</dt>
                    <dd class="font-medium text-ink tabular">{{ monthsToHuman(payoff[key].months_to_debt_free) }}</dd>
                  </div>
                  <div class="flex justify-between">
                    <dt class="text-ink-muted">Interest paid</dt>
                    <dd class="font-medium text-ink tabular">{{ money0(payoff[key].total_interest) }}</dd>
                  </div>
                </dl>
              </button>
            </div>

            <Alert variant="info" class="mt-4">{{ payoff.rationale }}</Alert>

            <div class="mt-6">
              <h3 class="mb-3 text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">
                Balance over time
              </h3>
              <LineChart :series="timelineSeries" :labels="timelineLabels" :height="200" />
            </div>
          </Card>

          <Card :title="`Payoff order (${strategy})`" subtitle="Send every spare dollar to the top one.">
            <ol class="space-y-2.5">
              <li v-for="(d, i) in ordered" :key="d.debt_id" class="flex items-start gap-3 rounded-lg border border-line p-3">
                <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[color:var(--primary-soft)] text-[12px] font-semibold text-primary">
                  {{ i + 1 }}
                </span>
                <div class="min-w-0 flex-1">
                  <p class="truncate text-[13px] font-medium text-ink">{{ d.name }}</p>
                  <p class="mt-0.5 text-[12px] text-ink-muted tabular">
                    Clear in {{ monthsToHuman(d.months_to_payoff) }} · {{ money0(d.interest_paid) }} interest
                  </p>
                </div>
              </li>
            </ol>
          </Card>
        </div>

        <Card class="mt-6" title="Your debts" flush>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-[13px]">
              <thead class="border-b border-line text-[12px] text-ink-muted">
                <tr>
                  <th scope="col" class="px-4 py-2.5 font-medium">Debt</th>
                  <th scope="col" class="hidden px-4 py-2.5 font-medium sm:table-cell">Type</th>
                  <th scope="col" class="px-4 py-2.5 text-right font-medium">Balance</th>
                  <th scope="col" class="px-4 py-2.5 text-right font-medium">APR</th>
                  <th scope="col" class="hidden px-4 py-2.5 text-right font-medium sm:table-cell">Minimum</th>
                  <th scope="col" class="px-4 py-2.5"><span class="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="debt in debts" :key="debt.id" class="border-b border-line last:border-0 hover:bg-raised">
                  <td class="px-4 py-3 font-medium text-ink">{{ debt.name }}</td>
                  <td class="hidden px-4 py-3 sm:table-cell">
                    <Badge size="sm">{{ titleCase(debt.debt_type) }}</Badge>
                  </td>
                  <td class="px-4 py-3 text-right text-ink tabular">{{ money0(debt.current_balance) }}</td>
                  <td class="px-4 py-3 text-right tabular"
                    :style="{ color: Number(debt.apr) >= 8 ? 'var(--critical-ink)' : 'var(--ink)' }">
                    {{ percent(debt.apr, 2) }}
                  </td>
                  <td class="hidden px-4 py-3 text-right text-ink-muted tabular sm:table-cell">
                    {{ money0(debt.minimum_payment) }}
                  </td>
                  <td class="whitespace-nowrap px-4 py-3 text-right">
                    <button type="button" class="rounded p-1 text-ink-subtle hover:text-ink" aria-label="Edit" @click="openEdit(debt)">
                      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none"><path d="M4 20h4L19 9l-4-4L4 16v4Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" /></svg>
                    </button>
                    <button type="button" class="rounded p-1 text-ink-subtle hover:text-[color:var(--critical-ink)]" aria-label="Delete" @click="remove(debt.id)">
                      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none"><path d="M5 7h14M9 7V5h6v2m-8 0 1 13h8l1-13" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card>
      </template>

      <EmptyState
        v-else
        title="No debts recorded"
        description="Add what you owe and Bearly will simulate both payoff strategies month by month, so you can see which clears it faster and which costs less."
      >
        <Button @click="openNew">Add your first debt</Button>
      </EmptyState>
    </PageState>

    <Dialog v-model:open="dialogOpen" :title="form.id ? 'Edit debt' : 'Add debt'">
      <form class="space-y-4" @submit.prevent="save">
        <p v-if="formError" class="text-[13px] text-[color:var(--critical-ink)]">{{ formError }}</p>

        <Input v-model="form.name" label="Name" required placeholder="e.g. Chase Sapphire" />
        <Select v-model="form.debt_type" label="Type" :options="DEBT_TYPES" />

        <div class="grid gap-4 sm:grid-cols-2">
          <Input v-model="form.current_balance" label="Current balance" money required />
          <Input v-model="form.apr" label="Interest rate (APR)" suffix="%" required
            hint="Found on your statement." />
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <Input v-model="form.minimum_payment" label="Minimum payment" money required />
          <Input v-model="form.due_day" label="Due day of month" type="number" min="1" max="31" placeholder="Optional" />
        </div>
      </form>

      <template #footer>
        <Button variant="ghost" @click="dialogOpen = false">Cancel</Button>
        <Button :loading="saving" @click="save">{{ form.id ? "Save changes" : "Add debt" }}</Button>
      </template>
    </Dialog>
  </div>
</template>
