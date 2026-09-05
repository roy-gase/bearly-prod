<script setup>
/**
 * In-app character avatar. Shoulders overflow the circle and are clipped.
 * Reduced (≤40px): drop brows, highlights, blush, and inner ears.
 */
import { computed } from "vue";

const props = defineProps({
  size: { type: [Number, String], default: 40 },
  detail: { type: String, default: "auto" }, // auto | full | reduced
  inverted: Boolean,
  composer: Boolean,
  label: { type: String, default: "Bearly" },
});

const px = computed(() => Number(props.size));
const reduced = computed(() =>
  props.detail === "reduced" || (props.detail === "auto" && px.value <= 40),
);

const badge = computed(() => {
  if (props.inverted) return "#8B5E34";
  if (props.composer) return "#F0D9B5";
  return "#F6E7CE";
});

const fur = computed(() => (props.inverted ? "#F0D9B5" : "#8B5E34"));
const innerEar = computed(() => (props.inverted ? "#8B5E34" : "#C89A6B"));
const muzzle = computed(() => (props.inverted ? "#F6E7CE" : "#F0D9B5"));
const shoulders = computed(() => (props.inverted ? "#C89A6B" : "#7A4F2A"));
</script>

<template>
  <svg
    :width="px"
    :height="px"
    viewBox="0 0 120 120"
    class="shrink-0"
    style="clip-path: circle(50%)"
    :aria-label="label"
    role="img"
  >
    <circle cx="60" cy="60" r="60" :fill="badge" />
    <ellipse cx="60" cy="122" rx="34" ry="26" :fill="shoulders" />

    <circle cx="27" cy="38" r="14" :fill="fur" />
    <circle v-if="!reduced" cx="27" cy="38" r="6.5" :fill="innerEar" />
    <circle cx="93" cy="38" r="14" :fill="fur" />
    <circle v-if="!reduced" cx="93" cy="38" r="6.5" :fill="innerEar" />

    <circle cx="60" cy="64" r="33" :fill="fur" />
    <ellipse
      cx="60"
      :cy="inverted ? 76 : 79"
      :rx="inverted ? 16 : 19"
      :ry="inverted ? 12 : 14"
      :fill="muzzle"
    />

    <g v-if="!reduced && !inverted">
      <path d="M40 51 Q46 47 52 50" fill="none" stroke="#5E3D1F" stroke-width="2.6" stroke-linecap="round" />
      <path d="M68 50 Q74 47 80 51" fill="none" stroke="#5E3D1F" stroke-width="2.6" stroke-linecap="round" />
    </g>

    <circle cx="46" :cy="inverted ? 58 : 61" :r="inverted ? 4.2 : 4.4" fill="#241A12" />
    <circle v-if="!reduced && !inverted" cx="47.3" cy="59.7" r="1.5" fill="#FFFDF9" />
    <circle cx="74" :cy="inverted ? 58 : 61" :r="inverted ? 4.2 : 4.4" fill="#241A12" />
    <circle v-if="!reduced && !inverted" cx="75.3" cy="59.7" r="1.5" fill="#FFFDF9" />

    <ellipse
      cx="60"
      :cy="inverted ? 70 : 72"
      :rx="inverted ? 5 : 5.6"
      :ry="inverted ? 4 : 4.4"
      fill="#241A12"
    />
    <path
      v-if="!inverted"
      d="M53 81 Q60 87 67 81"
      fill="none"
      stroke="#241A12"
      stroke-width="2.8"
      stroke-linecap="round"
    />

    <g v-if="!reduced && !inverted">
      <ellipse cx="36" cy="70" rx="6" ry="4.6" fill="#C4703C" opacity=".45" />
      <ellipse cx="84" cy="70" rx="6" ry="4.6" fill="#C4703C" opacity=".45" />
    </g>
  </svg>
</template>
