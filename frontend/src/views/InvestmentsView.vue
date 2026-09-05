<script setup>
/**
 * Investments are one component of the plan, not a trading screen.
 *
 * If the backend says the foundations are not in place, that message leads the
 * page — holdings and allocation come second.
 */
import { computed, onMounted, ref } from "vue";
import { api } from "@/lib/api";
import { money0, percent, titleCase } from "@/lib/format";
import { foldToSeries } from "@/lib/colors";

import PageState from "@/components/app/PageState.vue";
import Card from "@/components/ui/Card.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Select from "@/components/ui/Select.vue";
import Badge from "@/components/ui/Badge.vue";
import Alert from "@/components/ui/Alert.vue";
import Dialog from "@/components/ui/Dialog.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import AllocationBar from "@/components/charts/AllocationBar.vue";
import LineChart from "@/components/charts/LineChart.vue";

const loading = ref(true);
const error = ref("");
const holdings = ref([]);
const allocation = ref(null);
const projection = ref(null);

const ASSET_TYPES = [
  { value: "stock", label: "Stock" },
  { value: "etf", label: "ETF" },
  { value: "index_fund", label: "Index fund" },
  { value: "mutual_fund", label: "Mutual fund" },
  { value: "bond", label: "Bond" },
  { value: "cash", label: "Cash" },
  { value: "crypto", label: "Crypto" },
  { value: "other", label: "Other" },
];

const blank = () => ({
  id: null, ticker: "", name: "", asset_type: "etf", quantity: "",
  cost_basis: "", current_price: "", manual_value: "", sector: "", risk_category: "moderate",
});
const form = ref(blank());
const dialogOpen = ref(false);
const saving = ref(false);
const formError = ref("");

const projectionInput = ref({ monthly: "500", years: 20, rate: "7" });

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [h, a] = await Promise.all([api.get("/investments/holdings"), api.get("/investments/allocation")]);
    holdings.value = h;
    allocation.value = a;
    await runProjection();
  } catch (err) {
    error.value = err.message || "Could not load your investments.";
  } finally {
    loading.value = false;
  }
}

async function runProjection() {
  projection.value = await api.post("/investments/projection", {
    principal: allocation.value?.total_value ?? 0,
    monthly_contribution: Number(projectionInput.value.monthly) || 0,
    annual_return_pct: Number(projectionInput.value.rate) || 7,
    years: Number(projectionInput.value.years) || 20,
  });
}

onMounted(load);

function openNew() {
  form.value = blank();
  formError.value = "";
  dialogOpen.value = true;
}
function openEdit(holding) {
  form.value = {
    ...holding,
    ticker: holding.ticker ?? "",
    cost_basis: holding.cost_basis ?? "",
    current_price: holding.current_price ?? "",
    manual_value: holding.manual_value ?? "",
    sector: holding.sector ?? "",
  };
  formError.value = "";
  dialogOpen.value = true;
}

async function save() {
  saving.value = true;
  formError.value = "";
  try {
    const numeric = (v) => (v === "" || v === null ? null : Number(v));
    const body = {
      ticker: form.value.ticker || null,
      name: form.value.name,
      asset_type: form.value.asset_type,
      quantity: Number(form.value.quantity) || 0,
      cost_basis: numeric(form.value.cost_basis),
      current_price: numeric(form.value.current_price),
      manual_value: numeric(form.value.manual_value),
      sector: form.value.sector || null,
      risk_category: form.value.risk_category,
    };
    if (form.value.id) await api.patch(`/investments/holdings/${form.value.id}`, body);
    else await api.post("/investments/holdings", body);
    dialogOpen.value = false;
    await load();
  } catch (err) {
    formError.value = err.fieldErrors?.[0]?.message || err.message || "Could not save.";
  } finally {
    saving.value = false;
  }
}

async function remove(id) {
  await api.delete(`/investments/holdings/${id}`);
  await load();
}

function slices(source) {
  const rows = Object.entries(source ?? {})
    .map(([key, v]) => ({ label: titleCase(key), value: v.value }))
    .sort((a, b) => b.value - a.value);
  return foldToSeries(rows);
}

const byType = computed(() => slices(allocation.value?.by_asset_type));
const byRisk = computed(() => slices(allocation.value?.by_risk));
const bySector = computed(() => slices(allocation.value?.by_sector));

const projectionSeries = computed(() => {
  if (!projection.value) return [];
  return [
    {
      label: "Projected value",
      color: "var(--series-1)",
      points: projection.value.series.map((p) => ({ x: p.year, y: p.balance })),
    },
    {
      label: "Money you put in",
      color: "var(--series-4)",
      points: projection.value.series.map((p) => ({ x: p.year, y: p.contributed })),
    },
  ];
});
const projectionLabels = computed(() => projection.value?.series.map((p) => `${p.year}y`) ?? []);
</script>

<template>
  <div>
    <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-[22px] font-semibold tracking-tight text-ink">Investments</h1>
        <p class="mt-1 text-[14px] text-ink-muted">One part of your plan, in the context of the rest of it.</p>
      </div>
      <Button @click="openNew">Add holding</Button>
    </div>

    <PageState :loading="loading" :error="error">
      <template v-if="allocation">
        <!-- The readiness gate leads the page. -->
        <Alert
          v-if="!allocation.readiness.investing_appropriate"
          variant="warning"
          title="Investing is not your best next move right now"
          class="mb-6"
        >
          {{ allocation.readiness.blocked_reason }}
          <RouterLink :to="{ name: 'dashboard' }" class="ml-1 font-medium text-primary underline-offset-4 hover:underline">
            See your priorities
          </RouterLink>
        </Alert>
        <Alert v-else variant="good" title="Your foundations are in place" class="mb-6">
          With essentials covered, a funded emergency fund and no expensive debt, about
          {{ money0(allocation.readiness.surplus_available_monthly) }} a month is genuinely investable.
        </Alert>

        <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Portfolio value</p>
            <p class="mt-1.5 text-[20px] font-semibold text-ink tabular">{{ money0(allocation.total_value) }}</p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Cost basis</p>
            <p class="mt-1.5 text-[20px] font-semibold text-ink tabular">{{ money0(allocation.cost_basis) }}</p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Unrealised gain</p>
            <p
              class="mt-1.5 text-[20px] font-semibold tabular"
              :style="{ color: (allocation.unrealized_gain ?? 0) >= 0 ? 'var(--good-ink)' : 'var(--critical-ink)' }"
            >
              {{ allocation.unrealized_gain === null ? "—" : money0(allocation.unrealized_gain) }}
            </p>
          </div>
          <div class="rounded-xl border border-line bg-card p-4">
            <p class="text-[12px] text-ink-muted">Risk tolerance</p>
            <p class="mt-1.5 text-[20px] font-semibold text-ink">{{ titleCase(allocation.risk_tolerance) }}</p>
          </div>
        </div>

        <div v-if="holdings.length" class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card title="By asset class"><AllocationBar :slices="byType" /></Card>
          <Card title="By risk level"><AllocationBar :slices="byRisk" /></Card>
          <Card title="By sector">
            <AllocationBar v-if="bySector.length" :slices="bySector" />
            <p v-else class="py-6 text-center text-[13px] text-ink-muted">
              Add a sector to your holdings to see this breakdown.
            </p>
          </Card>
        </div>

        <Card v-if="holdings.length" class="mt-6" title="Holdings" flush>
          <template #action>
            <span class="px-5 text-[12px] text-ink-subtle">{{ allocation.market_data.note }}</span>
          </template>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-[13px]">
              <thead class="border-b border-line text-[12px] text-ink-muted">
                <tr>
                  <th scope="col" class="px-4 py-2.5 font-medium">Holding</th>
                  <th scope="col" class="hidden px-4 py-2.5 font-medium sm:table-cell">Type</th>
                  <th scope="col" class="hidden px-4 py-2.5 text-right font-medium md:table-cell">Quantity</th>
                  <th scope="col" class="px-4 py-2.5 text-right font-medium">Value</th>
                  <th scope="col" class="hidden px-4 py-2.5 text-right font-medium sm:table-cell">Gain</th>
                  <th scope="col" class="px-4 py-2.5"><span class="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="h in holdings" :key="h.id" class="border-b border-line last:border-0 hover:bg-raised">
                  <td class="px-4 py-3">
                    <p class="font-medium text-ink">{{ h.ticker || h.name }}</p>
                    <p v-if="h.ticker" class="text-[12px] text-ink-muted">{{ h.name }}</p>
                  </td>
                  <td class="hidden px-4 py-3 sm:table-cell"><Badge size="sm">{{ titleCase(h.asset_type) }}</Badge></td>
                  <td class="hidden px-4 py-3 text-right text-ink-muted tabular md:table-cell">{{ h.quantity }}</td>
                  <td class="px-4 py-3 text-right font-medium text-ink tabular">{{ money0(h.market_value) }}</td>
                  <td class="hidden px-4 py-3 text-right tabular sm:table-cell"
                    :style="{ color: (h.unrealized_gain ?? 0) >= 0 ? 'var(--good-ink)' : 'var(--critical-ink)' }">
                    {{ h.unrealized_gain === null ? "—" : money0(h.unrealized_gain) }}
                  </td>
                  <td class="whitespace-nowrap px-4 py-3 text-right">
                    <button type="button" class="rounded p-1 text-ink-subtle hover:text-ink" aria-label="Edit" @click="openEdit(h)">
                      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none"><path d="M4 20h4L19 9l-4-4L4 16v4Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" /></svg>
                    </button>
                    <button type="button" class="rounded p-1 text-ink-subtle hover:text-[color:var(--critical-ink)]" aria-label="Delete" @click="remove(h.id)">
                      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none"><path d="M5 7h14M9 7V5h6v2m-8 0 1 13h8l1-13" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card>

        <EmptyState
          v-else class="mt-6"
          title="No holdings recorded"
          description="Add what you hold — including a whole-account balance if you do not want to break it down — to see your allocation."
        >
          <Button @click="openNew">Add a holding</Button>
        </EmptyState>

        <Card class="mt-6" title="What steady investing could become"
          subtitle="A projection at a fixed assumed rate, not a forecast.">
          <div class="mb-5 grid gap-4 sm:grid-cols-3">
            <Input v-model="projectionInput.monthly" label="Monthly contribution" money @change="runProjection" />
            <Input v-model="projectionInput.rate" label="Assumed annual return" suffix="%" @change="runProjection" />
            <Input v-model="projectionInput.years" label="Years" type="number" min="1" max="60" @change="runProjection" />
          </div>

          <template v-if="projection">
            <div class="mb-4 grid grid-cols-3 gap-4">
              <div>
                <p class="text-[12px] text-ink-muted">Projected value</p>
                <p class="mt-1 text-[20px] font-semibold text-ink tabular">{{ money0(projection.future_value) }}</p>
              </div>
              <div>
                <p class="text-[12px] text-ink-muted">You put in</p>
                <p class="mt-1 text-[20px] font-semibold text-ink tabular">{{ money0(projection.total_contributed) }}</p>
              </div>
              <div>
                <p class="text-[12px] text-ink-muted">Growth</p>
                <p class="mt-1 text-[20px] font-semibold tabular" style="color: var(--good-ink)">
                  {{ money0(projection.growth) }}
                </p>
              </div>
            </div>

            <LineChart :series="projectionSeries" :labels="projectionLabels" :height="200" area />

            <p class="mt-4 text-[12px] leading-relaxed text-ink-subtle">{{ projection.disclaimer }}</p>
          </template>
        </Card>
      </template>
    </PageState>

    <Dialog v-model:open="dialogOpen" :title="form.id ? 'Edit holding' : 'Add holding'">
      <form class="space-y-4" @submit.prevent="save">
        <p v-if="formError" class="text-[13px] text-[color:var(--critical-ink)]">{{ formError }}</p>

        <div class="grid gap-4 sm:grid-cols-2">
          <Input v-model="form.ticker" label="Ticker" placeholder="e.g. VTI — optional" />
          <Select v-model="form.asset_type" label="Asset type" :options="ASSET_TYPES" />
        </div>

        <Input v-model="form.name" label="Name" required placeholder="e.g. Vanguard Total Stock Market" />

        <div class="grid gap-4 sm:grid-cols-3">
          <Input v-model="form.quantity" label="Quantity" type="number" step="0.000001" min="0" />
          <Input v-model="form.current_price" label="Price per unit" money />
          <Input v-model="form.cost_basis" label="Cost basis" money hint="Optional" />
        </div>

        <Input
          v-model="form.manual_value" label="Or enter total value directly" money
          hint="Use this for a whole-account balance you do not want to break into units."
        />

        <div class="grid gap-4 sm:grid-cols-2">
          <Input v-model="form.sector" label="Sector" placeholder="Optional" />
          <Select
            v-model="form.risk_category" label="Risk level"
            :options="[
              { value: 'low', label: 'Low' },
              { value: 'moderate', label: 'Moderate' },
              { value: 'high', label: 'High' },
            ]"
          />
        </div>
      </form>

      <template #footer>
        <Button variant="ghost" @click="dialogOpen = false">Cancel</Button>
        <Button :loading="saving" @click="save">{{ form.id ? "Save changes" : "Add holding" }}</Button>
      </template>
    </Dialog>
  </div>
</template>
