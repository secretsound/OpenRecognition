<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { NInput, NModal } from "naive-ui";
import { api } from "@/api/client";
import type { EnrollmentOut } from "@/types/api";
import { canAdmin } from "@/utils/roles";
import { useAuth } from "@/composables/useAuth";
import { t } from "@/i18n";

const show = defineModel<boolean>("show", { default: false });

const router = useRouter();
const { role } = useAuth();
const query = ref("");
const enrollments = ref<EnrollmentOut[]>([]);
const active = ref(0);

const pages = computed(() => {
  const items = [
    { label: t("nav.overview"), to: "/", hint: t("palette.home") },
    { label: t("nav.library"), to: "/enrollments", hint: t("palette.profiles") },
    { label: t("nav.new"), to: "/enrollments/new", hint: t("palette.new") },
    { label: t("nav.recognize"), to: "/test", hint: t("palette.recognize") },
    { label: t("nav.activity"), to: "/logs" },
    { label: t("nav.connections"), to: "/integrations" },
    { label: t("nav.users"), to: "/users" },
    { label: t("nav.apiKeys"), to: "/keys" },
    { label: t("nav.settings"), to: "/settings" },
  ];
  if (canAdmin(role.value)) {
    items.splice(items.findIndex((i) => i.to === "/keys"), 0, { label: t("nav.groups"), to: "/groups" });
    items.push({ label: t("nav.models"), to: "/models" });
  }
  return items;
});

const results = computed(() => {
  const q = query.value.trim().toLowerCase();
  const pageHits = pages.value
    .filter((p) => !q || p.label.toLowerCase().includes(q) || (p.hint ?? "").toLowerCase().includes(q))
    .map((p) => ({ kind: "page" as const, ...p }));
  const people = enrollments.value
    .filter((e) => !q || e.label.toLowerCase().includes(q) || e.type.includes(q))
    .slice(0, 8)
    .map((e) => ({
      kind: "profile" as const,
      label: e.label,
      to: `/enrollments/${e.id}`,
      hint: e.type,
    }));
  return [...pageHits, ...people];
});

watch(results, () => {
  active.value = 0;
});

watch(show, async (open) => {
  if (!open) return;
  query.value = "";
  active.value = 0;
  try {
    enrollments.value = await api<EnrollmentOut[]>("/v1/enrollments");
  } catch {
    enrollments.value = [];
  }
});

function go(to: string) {
  show.value = false;
  void router.push(to);
}

function onKey(e: KeyboardEvent) {
  if (e.key === "ArrowDown") {
    e.preventDefault();
    active.value = Math.min(results.value.length - 1, active.value + 1);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    active.value = Math.max(0, active.value - 1);
  } else if (e.key === "Enter") {
    e.preventDefault();
    const hit = results.value[active.value];
    if (hit) go(hit.to);
  }
}

onMounted(() => {
  window.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      show.value = !show.value;
    }
  });
});
</script>

<template>
  <NModal
    v-model:show="show"
    class="or-palette-modal"
    :auto-focus="false"
    :trap-focus="true"
    preset="card"
    :bordered="false"
    style="width: min(92vw, 520px)"
  >
    <NInput
      v-model:value="query"
      size="large"
      :placeholder="t('palette.placeholder')"
      autofocus
      @keydown="onKey"
    />
    <ul class="or-palette" role="listbox">
      <li
        v-for="(hit, i) in results"
        :key="hit.to + hit.label"
        class="or-palette__item"
        :class="{ 'is-active': i === active }"
        role="option"
        :aria-selected="i === active"
        @mousedown.prevent="go(hit.to)"
      >
        <span>{{ hit.label }}</span>
        <span v-if="hit.hint" class="or-muted or-small">{{ hit.hint }}</span>
      </li>
      <li v-if="!results.length" class="or-palette__empty or-muted">{{ t("palette.empty") }}</li>
    </ul>
  </NModal>
</template>
