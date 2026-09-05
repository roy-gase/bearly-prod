<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { api } from "@/lib/api";
import { money0, moneySigned, percent, MONTH_NAMES, titleCase } from "@/lib/format";
import { FLOW, foldToSeries } from "@/lib/colors";
import GroupedBarChart from "@/components/charts/GroupedBarChart.vue";

import PageState from "@/components/app/PageState.vue";
import Card from "@/components/ui/Card.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Select from "@/components/ui/Select.vue";
import Badge from "@/components/ui/Badge.vue";
import Alert from "@/components/ui/Alert.vue";
import Dialog from "@/components/ui/Dialog.vue";
import BudgetBars from "@/components/charts/BudgetBars.vue";
import AllocationBar from "@/components/charts/AllocationBar.vue";

const today = new Date();
const year = ref(today.getFullYear());
const month = ref(today.getMonth() + 1);

const loading = ref(true);
const error = ref("");
const saving = ref(false);
const budget = ref(null);
const history = ref([]);
const categories = ref([]);
const drafts = ref({});
const expectedIncome = ref("");
const editing = ref(false);
const newCategory = ref({ open: false, name: "", kind: "discretionary" });

const monthOptions = MONTH_NAMES.map((label, i) => ({ value: String(i + 1), label }));
const yearOptions = Array.from({ length: 5 }, (_, i) => {
  const y = today.getFullYear() - 2 + i;
  return { value: String(y), label: String(y) };
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const windows = lastNMonths(year.value, month.value, 6);
    const [b, c, ...past] = await Promise.all([
      api.get("/budgets", { year: year.value, month: month.value }),
      api.get("/budgets/categories"),
      ...windows.slice(0, -1).map((w) => api.get("/budgets", w)),
    ]);
    budget.value = b;
    history.value = [...past, b];
    categories.value = c;
    expectedIncome.value = b.expected_income || "";
    drafts.value = Object.fromEntries(
      c.map((cat) => [cat.id, b.lines.find((l) => l.category_id === cat.id)?.budgeted ?? ""]),
    );
  } catch (err) {
    error.value = err.message || "Could not load your budget.";
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const lines = Object.entries(drafts.value)
      .filter(([, value]) => Number(value) > 0)
      .map(([category_id, value]) => ({ category_id: Number(category_id), budgeted_amount: Number(value) }));
    budget.value = await api.put("/budgets", {
      year: year.value,
      month: month.value,
      expected_income: Number(expectedIncome.value) || 0,
      lines,
    });
    editing.value = false;
  } catch (err) {
    error.value = err.message;
  } finally {
    saving.value = false;
  }
}

async function copyPrevious() {
  saving.value = true;
  try {
    budget.value = await api.post(`/budgets/copy-previous?year=${year.value}&month=${month.value}`);
    await load();
  } catch (err) {
    error.value = err.message || "No budget found for last month.";
  } finally {
    saving.value = false;
  }
}

async function addCategory() {
  await api.post("/budgets/categories", {
    name: newCategory.value.name,
    kind: newCategory.value.kind,
  });
  newCategory.value = { open: false, name: "", kind: "discretionary" };
  await load();
}

watch([year, month], load);
onMounted(load);

function lastNMonths(y, m, n) {
  const out = [];
  let year = y;
  let month = m;
  for (let i = 0; i < n; i++) {
    out.unshift({ year, month });
    month -= 1;
    if (month === 0) {
      month = 12;
      year -= 1;
    }
  }
  return out;
}

const draftTotal = computed(() =>
  Object.values(drafts.value).reduce((sum, v) => sum + (Number(v) || 0), 0),
);
const unallocated = computed(() => (Number(expectedIncome.value) || 0) - draftTotal.value);

const spendSlices = computed(() => {
  if (!budget.value) return [];
  const rows = budget.value.lines
    .filter((l) => l.actual > 0)
    .map((l) => ({ label: l.name, value: l.actual }))
    .sort((a, b) => b.value - a.value);
  return foldToSeries(rows);
});

const kindSlices = computed(() => {
  if (!budget.value) return [];
  const totals = new Map();
  for (const line of budget.value.lines) {
    if (line.actual <= 0) continue;
    const key = titleCase(line.kind);
    totals.set(key, (totals.get(key) || 0) + line.actual);
  }
  const rows = [...totals.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
  return foldToSeries(rows);
});

const incomeSlices = computed(() => {
  if (!budget.value || budget.value.total_income <= 0) return [];
  const leftover = Math.max(0, budget.value.remaining_cash);
  const rows = [
    { label: "Spent", value: budget.value.total_spent },
    { label: "Left over", value: leftover },
  ].filter((row) => row.value > 0);
  return foldToSeries(rows);
});

const planVsActual = computed(() => {
  if (!budget.value) return [];
  return budget.value.lines
    .filter((l) => l.budgeted > 0 || l.actual > 0)
    .sort((a, b) => Math.max(b.budgeted, b.actual) - Math.max(a.budgeted, a.actual))
    .slice(0, 8)
    .map((l) => ({
      label: l.name.length > 12 ? `${l.name.slice(0, 11)}…` : l.name,
      values: [l.budgeted, l.actual],
    }));
});

const historyGroups = computed(() =>
  history.value.map((b) => ({
    label: MONTH_NAMES[b.month - 1].slice(0, 3),
    values: [b.total_budgeted, b.total_spent],
  })),
);
const hasHistory = computed(() =>
  history.value.some((b) => b.total_budgeted > 0 || b.total_spent > 0),
);

const variance = computed(() => {
  if (!budget.value) return [];
  return [...budget.value.lines]
    .filter((l) => l.budgeted > 0 || l.actual > 0)
    .sort((a, b) => a.remaining - b.remaining);
});

const overspent = computed(() => budget.value?.lines.filter((l) => l.is_over) ?? []);
const underspent = computed(() =>
  (budget.value?.lines ?? []).filter((l) => l.budgeted > 0 && !l.is_over && l.remaining > 0),
);
</script>

<template>
  <div>
    <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-[22px] font-semibold tracking-tight text-ink">Budget</h1>
        <p class="mt-1 text-[14px] text-ink-muted">Plan what goes where, then see how it actually went.</p>
      </div>
      <div class="flex items-end gap-2">
        <Select v-model="month" :options="monthOptions" class="w-32" />
        <Select v-model="year" :options="yearOptions" class="w-24" />
      </div>
    </div>

    <PageState :loading="loading" :error="error">
      <template v-if="budget">
        <!-- Summary row -->
        <div class="grid grid-cols-2 gap-4 lg:grid-cols-5">
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Expected income</p>
            <p class="mt-1.5 text-[20px] font-semibold text-ink tabular">{{ money0(budget.total_income) }}</p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Budgeted</p>
            <p class="mt-1.5 text-[20px] font-semibold text-ink tabular">{{ money0(budget.total_budgeted) }}</p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Spent</p>
            <p class="mt-1.5 text-[20px] font-semibold text-ink tabular">{{ money0(budget.total_spent) }}</p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Remaining cash</p>
            <p
              class="mt-1.5 text-[20px] font-semibold tabular"
              :style="{ color: budget.remaining_cash >= 0 ? 'var(--ink)' : 'var(--critical-ink)' }"
            >{{ money0(budget.remaining_cash) }}</p>
          </div>
          <div class="col-span-2 rounded-xl border border-line bg-card p-4 lg:col-span-1">
            <p class="text-[12px] text-ink-muted">Savings rate</p>
            <p class="mt-1.5 text-[20px] font-semibold text-ink tabular">{{ percent(budget.savings_rate_pct) }}</p>
          </div>
        </div>

        <Alert v-if="overspent.length" variant="warning" class="mt-6"
          :title="`${overspent.length} ${overspent.length === 1 ? 'category is' : 'categories are'} over plan`">
          {{ overspent.map((l) => l.name).join(", ") }}
        </Alert>

        <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="Planned vs actual" subtitle="The eight largest categories this month.">
            <GroupedBarChart
              v-if="planVsActual.length"
              :series="[
                { label: 'Planned', color: FLOW.net },
                { label: 'Spent', color: FLOW.expense },
              ]"
              :groups="planVsActual"
            />
            <p v-else class="py-8 text-center text-[13px] text-ink-muted">
              Set a plan or log spending to compare the two.
            </p>
          </Card>

          <Card title="Six-month trend" subtitle="Budgeted and spent for this month and the five before it.">
            <GroupedBarChart
              v-if="hasHistory"
              :series="[
                { label: 'Budgeted', color: FLOW.net },
                { label: 'Spent', color: FLOW.expense },
              ]"
              :groups="historyGroups"
            />
            <p v-else class="py-8 text-center text-[13px] text-ink-muted">
              Earlier months will appear here once there is a plan or spending.
            </p>
          </Card>
        </div>

        <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card title="Spending by type" subtitle="Essential, discretionary, and the rest.">
            <AllocationBar v-if="kindSlices.length" :slices="kindSlices" />
            <p v-else class="py-6 text-center text-[13px] text-ink-muted">
              No spending recorded for this month yet.
            </p>
          </Card>

          <Card title="Where income went" subtitle="Spent versus left over from expected income.">
            <AllocationBar v-if="incomeSlices.length" :slices="incomeSlices" />
            <p v-else class="py-6 text-center text-[13px] text-ink-muted">
              Add expected income to see this split.
            </p>
          </Card>

          <Card title="Variance" subtitle="Furthest from plan, overspend first.">
            <ul v-if="variance.length" class="space-y-2.5">
              <li v-for="row in variance.slice(0, 6)" :key="row.name" class="flex items-baseline justify-between gap-3">
                <span class="truncate text-[13px] text-ink">{{ row.name }}</span>
                <span
                  class="shrink-0 text-[13px] font-medium tabular"
                  :style="{ color: row.remaining < 0 ? 'var(--critical-ink)' : 'var(--good-ink)' }"
                >{{ moneySigned(row.remaining) }}</span>
              </li>
            </ul>
            <p v-else class="py-6 text-center text-[13px] text-ink-muted">
              Nothing to compare yet.
            </p>
            <p v-if="underspent.length && overspent.length" class="mt-3 border-t border-line pt-3 text-[12px] text-ink-muted">
              {{ overspent.length }} over · {{ underspent.length }} still under plan
            </p>
          </Card>
        </div>

        <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card class="lg:col-span-2" title="Categories"
            :subtitle="editing ? 'Set what you plan to spend in each category.' : 'Planned versus actual for this month.'">
            <template #action>
              <div class="flex gap-2">
                <Button v-if="!editing" variant="secondary" size="sm" @click="editing = true">Edit plan</Button>
                <template v-else>
                  <Button variant="ghost" size="sm" @click="editing = false; load()">Cancel</Button>
                  <Button size="sm" :loading="saving" @click="save">Save</Button>
                </template>
              </div>
            </template>

            <div v-if="editing" class="space-y-4">
              <Input v-model="expectedIncome" label="Expected income this month" money />

              <div class="rounded-lg border border-line bg-page p-3">
                <div class="flex items-center justify-between text-[13px]">
                  <span class="text-ink-muted">Unallocated</span>
                  <span
                    class="font-semibold tabular"
                    :style="{ color: unallocated >= 0 ? 'var(--good-ink)' : 'var(--critical-ink)' }"
                  >{{ money0(unallocated) }}</span>
                </div>
                <p v-if="unallocated < 0" class="mt-1 text-[12px] text-ink-muted">
                  You have budgeted more than you expect to earn.
                </p>
              </div>

              <div class="space-y-2.5">
                <div v-for="cat in categories" :key="cat.id" class="flex items-center gap-3">
                  <span class="flex-1 truncate text-[13px] text-ink">{{ cat.name }}</span>
                  <Badge size="sm">{{ cat.kind }}</Badge>
                  <div class="w-32"><Input v-model="drafts[cat.id]" money placeholder="0" /></div>
                </div>
              </div>

              <Button variant="ghost" size="sm" @click="newCategory.open = true">+ Add a category</Button>
            </div>

            <div v-else>
              <BudgetBars v-if="budget.lines.length" :rows="budget.lines" />
              <div v-else class="py-8 text-center">
                <p class="text-[13px] text-ink-muted">
                  No budget set for {{ MONTH_NAMES[month - 1] }} and nothing spent yet.
                </p>
                <div class="mt-3 flex justify-center gap-2">
                  <Button size="sm" @click="editing = true">Set a budget</Button>
                  <Button variant="secondary" size="sm" :loading="saving" @click="copyPrevious">
                    Copy last month
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          <Card title="Where money went" subtitle="Actual spending this month.">
            <AllocationBar v-if="spendSlices.length" :slices="spendSlices" />
            <p v-else class="py-6 text-center text-[13px] text-ink-muted">
              No spending recorded for this month yet.
            </p>
          </Card>
        </div>
      </template>
    </PageState>

    <Dialog v-model:open="newCategory.open" title="Add a category">
      <div class="space-y-4">
        <Input v-model="newCategory.name" label="Name" placeholder="e.g. Pet care" required />
        <Select
          v-model="newCategory.kind" label="Type"
          hint="This tells Bearly whether the spending is essential when calculating your emergency fund."
          :options="[
            { value: 'essential', label: 'Essential' },
            { value: 'discretionary', label: 'Discretionary' },
            { value: 'debt', label: 'Debt payment' },
            { value: 'savings', label: 'Savings' },
            { value: 'investment', label: 'Investment' },
            { value: 'other', label: 'Other' },
          ]"
        />
      </div>
      <template #footer>
        <Button variant="ghost" @click="newCategory.open = false">Cancel</Button>
        <Button :disabled="!newCategory.name" @click="addCategory">Add category</Button>
      </template>
    </Dialog>
  </div>
</template>
