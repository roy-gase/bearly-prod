<script setup>
/**
 * Animated chat avatar. State: idle | listening | thinking.
 * Motion is CSS on nested groups; reduced-motion falls back to the static face.
 */
import { computed } from "vue";

const props = defineProps({
  size: { type: [Number, String], default: 40 },
  state: { type: String, default: "idle" }, // idle | listening | thinking
  composer: Boolean,
  label: { type: String, default: "Bearly" },
});

const px = computed(() => Number(props.size));
const thinking = computed(() => props.state === "thinking");
const listening = computed(() => props.state === "listening");
const reduced = computed(() => px.value <= 40);
const wrap = computed(() => px.value);

const badge = computed(() => {
  if (thinking.value) return "#8B5E34";
  if (props.composer) return "#F0D9B5";
  return "#F6E7CE";
});
const fur = computed(() => (thinking.value ? "#F0D9B5" : "#8B5E34"));
const innerEar = computed(() => (thinking.value ? "#8B5E34" : "#C89A6B"));
const muzzle = computed(() => (thinking.value ? "#F6E7CE" : "#F0D9B5"));
const shoulders = computed(() => (thinking.value ? "#C89A6B" : "#7A4F2A"));
const blinkDuration = computed(() => (thinking.value ? "4.4s" : "5.6s"));
</script>

<template>
  <div
    class="relative inline-flex shrink-0 items-center justify-center"
    :style="{ width: `${wrap}px`, height: `${wrap}px` }"
  >
    <div
      v-if="listening"
      class="pointer-events-none absolute -inset-[4px] rounded-full border-2 border-[#C89A6B] [animation:bl-ring_2.6s_ease-out_infinite]"
      aria-hidden="true"
    />
    <svg
      :width="px"
      :height="px"
      viewBox="0 0 120 120"
      class="bear-live shrink-0"
      style="clip-path: circle(50%)"
      :aria-label="label"
      role="img"
    >
      <circle cx="60" cy="60" r="60" :fill="badge" />
      <g class="bl-sway">
        <ellipse cx="60" cy="122" rx="34" ry="26" :fill="shoulders" />
        <g class="bl-breathe">
          <g class="bl-ear-l">
            <circle cx="27" cy="38" r="14" :fill="fur" />
            <circle v-if="!reduced && !thinking" cx="27" cy="38" r="6.5" :fill="innerEar" />
          </g>
          <g class="bl-ear-r">
            <circle cx="93" cy="38" r="14" :fill="fur" />
            <circle v-if="!reduced && !thinking" cx="93" cy="38" r="6.5" :fill="innerEar" />
          </g>
          <circle cx="60" cy="64" r="33" :fill="fur" />
          <ellipse
            cx="60"
            :cy="thinking ? 76 : 79"
            :rx="thinking ? 16 : 19"
            :ry="thinking ? 12 : 14"
            :fill="muzzle"
          />
          <g v-if="!reduced && !thinking" class="bl-brow">
            <path d="M40 51 Q46 47 52 50" fill="none" stroke="#5E3D1F" stroke-width="2.6" stroke-linecap="round" />
            <path d="M68 50 Q74 47 80 51" fill="none" stroke="#5E3D1F" stroke-width="2.6" stroke-linecap="round" />
          </g>
          <g class="bl-blink" :style="{ animationDuration: blinkDuration }">
            <circle cx="46" :cy="thinking ? 58 : 61" :r="thinking ? 4.2 : 4.4" fill="#241A12" />
            <circle v-if="!reduced && !thinking" cx="47.3" cy="59.7" r="1.5" fill="#FFFDF9" />
            <circle cx="74" :cy="thinking ? 58 : 61" :r="thinking ? 4.2 : 4.4" fill="#241A12" />
            <circle v-if="!reduced && !thinking" cx="75.3" cy="59.7" r="1.5" fill="#FFFDF9" />
          </g>
          <ellipse
            cx="60"
            :cy="thinking ? 70 : 72"
            :rx="thinking ? 5 : 5.6"
            :ry="thinking ? 4 : 4.4"
            fill="#241A12"
          />
          <path
            v-if="!thinking"
            d="M53 81 Q60 87 67 81"
            fill="none"
            stroke="#241A12"
            stroke-width="2.8"
            stroke-linecap="round"
          />
          <g v-if="!reduced && !thinking">
            <ellipse cx="36" cy="70" rx="6" ry="4.6" fill="#C4703C" opacity=".45" />
            <ellipse cx="84" cy="70" rx="6" ry="4.6" fill="#C4703C" opacity=".45" />
          </g>
        </g>
      </g>
    </svg>
  </div>
</template>
