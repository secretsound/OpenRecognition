<script setup lang="ts">
import { computed, h, onMounted, ref, watch, type Component, type VNode } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NTag,
  NAlert,
  NSkeleton,
  NPopconfirm,
  NIcon,
  NSelect,
  NInput,
  NDataTable,
  NDropdown,
  NModal,
  NTooltip,
  NForm,
  NFormItem,
  NInputNumber,
  useDialog,
  useMessage,
} from "naive-ui";
import type { DataTableColumns, SelectOption } from "naive-ui";
import { CloudDownloadOutline, CreateOutline, EllipsisHorizontalOutline } from "@vicons/ionicons5";
import { api } from "@/api/client";
import type {
  InferenceBackend,
  ModelCatalogEntry,
  ModelDownloadResponse,
  ModelsStatusOut,
} from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
import { ApiError } from "@/api/client";
import { useAuth } from "@/composables/useAuth";

const message = useMessage();
const dialog = useDialog();
const router = useRouter();
const { role } = useAuth();

const loading = ref(true);
const downloading = ref(false);
const downloadingKey = ref<string | null>(null);
const deletingKey = ref<string | null>(null);
const reloading = ref(false);
const status = ref<ModelsStatusOut | null>(null);
const inferenceDraft = ref<InferenceBackend>("auto");
const savingInference = ref(false);
const search = ref("");
const groupFilter = ref<string | null>(null);
const statusFilter = ref<string | null>(null);
const showModelForm = ref(false);
const editingKey = ref<string | null>(null);
const savingModel = ref(false);
const usingKey = ref<string | null>(null);
const formLabel = ref("");
const formCategory = ref("voice_match");
const formVersion = ref("");
const formUrl = ref("");
const formOnnx = ref<Record<string, string | number>>({});
const hardwareDraft = ref("auto");
const savingHardware = ref(false);
const threadDraft = ref<number | null>(null);
const savingThreads = ref(false);
const showSettings = ref(false);
const showAbout = ref(false);
const aboutRow = ref<ModelCatalogEntry | null>(null);
type AboutTab = "overview" | "others";
const aboutTab = ref<AboutTab>("overview");
const pickedKey = ref<string | null>(null);
const settingsRow = ref<ModelCatalogEntry | null>(null);
const knobDraft = ref<Record<string, number>>({});
const contractDraft = ref<Record<string, string | number | boolean>>({});
const savingKnobs = ref(false);
const PAGE_SIZE = 16;
const shownCount = ref(PAGE_SIZE);
type ModelSection = "recommended" | "catalog" | "settings";
const sectionTab = ref<ModelSection>("recommended");
const sectionTabs: { value: ModelSection; label: string }[] = [
  { value: "recommended", label: "Recommended" },
  { value: "catalog", label: "All models" },
  { value: "settings", label: "Settings" },
];

const categoryBenefits: Record<string, string> = {
  speech_check:
    "Music, silence, and background noise stop here, so speaker matching only runs on speech.",
  voice_match:
    "Voice enrollments, audio recognition, and Wyoming use this model to name the speaker.",
  skip_reasons:
    "A skipped clip can say music, silence, or noise, which makes the gate easier to tune.",
  find_face:
    "The face is cropped out of the photo first, so matching holds up better in groups and busy rooms.",
  match_face: "Photo enrollments and image recognition use this model to name the person.",
  find_pet:
    "The pet or object is cropped out of the photo first, instead of guessing from the whole frame.",
  match_pet: "Pet and object enrollments and image recognition use this model to name what was found.",
};

const settingLabels: Record<string, string> = {
  embed_dim: "Embedding size",
  input_size: "Input size",
  conf_thres: "Minimum score",
  input_norm: "Color scaling",
  preprocessor: "Audio preparation",
  sample_rate: "Sample rate",
  num_mel_bins: "Mel bands",
  max_seconds: "Max length (seconds)",
  backend: "File type",
};

const inferenceOptions: SelectOption[] = [
  { label: "Automatic", value: "auto" },
  { label: "Downloaded files", value: "onnx" },
  { label: "Built-in guess", value: "heuristic" },
];

const statusOptions: SelectOption[] = [
  { label: "In use", value: "active" },
  { label: "Still matching", value: "kept" },
  { label: "Ready", value: "ready" },
  { label: "Not downloaded", value: "missing" },
];

const suggestedMissing = computed(
  () => status.value?.presets.find((preset) => preset.id === "full")?.missing_keys ?? [],
);

const catalogByKey = computed(() => {
  const map = new Map<string, ModelCatalogEntry>();
  for (const row of status.value?.catalog ?? []) {
    map.set(row.key, row);
  }
  return map;
});

const groupOptions = computed<SelectOption[]>(() =>
  [...(status.value?.categories ?? [])]
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((cat) => ({ label: cat.label, value: cat.id })),
);

const hardwareOptions = computed<SelectOption[]>(() => {
  const detected = status.value?.hardware.detected;
  const detectedLabel = detected ? machineLabel(detected) : "this machine";
  return [
    { label: `Automatic (${detectedLabel})`, value: "auto" },
    { label: "Raspberry Pi", value: "pi" },
    { label: "Mini PC", value: "mini" },
    { label: "Desktop", value: "desktop" },
    { label: "Server", value: "server" },
  ];
});

function modelTitle(row: ModelCatalogEntry): string {
  return row.label || row.use_for;
}

function categoryLabel(id: string): string {
  return status.value?.categories.find((cat) => cat.id === id)?.label || id;
}

function categoryOrder(id: string): number {
  return status.value?.categories.find((cat) => cat.id === id)?.sort_order ?? 0;
}

function machineLabel(tier: string): string {
  if (tier === "pi") return "Raspberry Pi";
  if (tier === "mini") return "Mini PC";
  if (tier === "desktop") return "Desktop";
  if (tier === "server") return "Server";
  return tier;
}

function memoryText(mb: number): string {
  if (!mb) return "memory unknown";
  if (mb >= 1024) {
    const gb = mb / 1024;
    return `${gb >= 10 ? Math.round(gb) : gb.toFixed(1)} GB`;
  }
  return `${mb} MB`;
}

function fitLabel(row: ModelCatalogEntry): string | null {
  if (row.suggested) return "Suggested";
  if (row.fit === "heavier") return "Heavier";
  if (row.fit === "lighter") return "Lighter";
  return null;
}

function fitText(row: ModelCatalogEntry): string {
  return row.fit === "heavier" ? "Too heavy" : "Can run";
}

function diskBytes(row: ModelCatalogEntry): number {
  if (row.on_disk && row.size_bytes) return row.size_bytes;
  return row.disk_bytes || 0;
}

function memoryLabel(row: ModelCatalogEntry): string {
  const mb = row.memory_mb || 0;
  if (!mb) return "";
  return `about ${memoryText(mb)}`;
}

function categoryMates(row: ModelCatalogEntry): ModelCatalogEntry[] {
  const order: Record<string, number> = { pi: 0, mini: 1, desktop: 2, server: 3 };
  return (status.value?.catalog ?? [])
    .filter((item) => item.category === row.category)
    .slice()
    .sort(
      (a, b) =>
        (order[a.hardware || "pi"] ?? 0) - (order[b.hardware || "pi"] ?? 0) ||
        a.sort_order - b.sort_order,
    );
}

const otherMates = computed(() => {
  const row = aboutRow.value;
  if (!row) return [];
  return categoryMates(row).filter((mate) => mate.key !== row.key);
});

const aboutTabs = computed(() => {
  const others = otherMates.value.length;
  return [
    { value: "overview" as const, label: "Overview" },
    { value: "others" as const, label: others ? `Similar models (${others})` : "Similar models" },
  ];
});

const pickedMate = computed(() =>
  pickedKey.value ? (catalogByKey.value.get(pickedKey.value) ?? null) : null,
);

const displayRow = computed(() => {
  if (aboutTab.value === "others" && pickedMate.value) return pickedMate.value;
  return aboutRow.value;
});

function modelRowProps(row: ModelCatalogEntry) {
  return {
    style: "cursor: pointer",
    onClick: () => openAbout(row),
  };
}

function openAbout(row: ModelCatalogEntry) {
  aboutRow.value = row;
  aboutTab.value = "overview";
  pickedKey.value = null;
  showAbout.value = true;
}

function selectMate(row: ModelCatalogEntry) {
  pickedKey.value = row.key;
}

function missingDeps(row: ModelCatalogEntry): string[] {
  return row.depends_on.filter((dep) => !catalogByKey.value.get(dep)?.on_disk);
}

const filteredRows = computed(() => {
  let list = status.value?.catalog ?? [];
  const query = search.value.trim().toLowerCase();
  if (query) {
    list = list.filter((row) =>
      [
        modelTitle(row),
        row.version || "",
        row.use_for,
        enableLines(row).join(" "),
        categoryLabel(row.category),
        machineLabel(row.hardware || ""),
      ]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }
  if (groupFilter.value) list = list.filter((row) => row.category === groupFilter.value);
  if (statusFilter.value === "ready") list = list.filter((row) => row.on_disk);
  if (statusFilter.value === "missing") list = list.filter((row) => !row.on_disk);
  if (statusFilter.value === "active") list = list.filter((row) => row.active);
  if (statusFilter.value === "kept") list = list.filter((row) => !row.active && keptCount(row) > 0);
  return [...list].sort(
    (a, b) =>
      categoryOrder(a.category) - categoryOrder(b.category) ||
      a.sort_order - b.sort_order ||
      modelTitle(a).localeCompare(modelTitle(b)),
  );
});

const filtersActive = computed(
  () =>
    search.value.trim().length > 0 ||
    groupFilter.value != null ||
    statusFilter.value != null,
);

function clearFilters() {
  search.value = "";
  groupFilter.value = null;
  statusFilter.value = null;
}

const categoryCards = computed(() =>
  [...(status.value?.categories ?? [])]
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((category) => {
      const rows = (status.value?.catalog ?? []).filter((row) => row.category === category.id);
      const downloadCount = rows.filter((row) => row.on_disk).length;
      return {
        id: category.id,
        label: category.label,
        summary: category.description,
        benefit: categoryBenefits[category.id] ?? "",
        downloaded: downloadCount > 0,
        downloadCount,
      };
    }),
);

function categoryStatus(card: { downloaded: boolean; downloadCount: number }): string {
  if (!card.downloaded) return "Not downloaded";
  return card.downloadCount === 1 ? "1 model downloaded" : `${card.downloadCount} models downloaded`;
}

function showCategory(id: string) {
  groupFilter.value = id;
  statusFilter.value = null;
  search.value = "";
  sectionTab.value = "catalog";
}

const recommendedRows = computed(() => {
  const categories = [...(status.value?.categories ?? [])].sort(
    (a, b) => a.sort_order - b.sort_order,
  );
  const rows: ModelCatalogEntry[] = [];
  for (const category of categories) {
    const match = status.value?.catalog.find(
      (row) => row.category === category.id && row.suggested,
    );
    if (match) rows.push(match);
  }
  return rows;
});

const suggestedPlan = computed(() => {
  const rows = recommendedRows.value;
  return {
    disk: rows.reduce((sum, row) => sum + (row.disk_bytes || 0), 0),
    memory: rows.reduce((sum, row) => sum + (row.memory_mb || 0), 0),
  };
});

const tableRows = computed(() => filteredRows.value.slice(0, shownCount.value));
const hasMoreModels = computed(() => shownCount.value < filteredRows.value.length);
const modelCountLabel = computed(() => {
  const shown = tableRows.value.length;
  const matched = filteredRows.value.length;
  const total = status.value?.catalog.length ?? matched;
  const nounCount = shown !== matched ? matched : matched !== total ? total : shown;
  const noun = `model${nounCount === 1 ? "" : "s"}`;
  if (shown !== matched) return `${shown} of ${matched} ${noun}`;
  if (matched !== total) return `${shown} of ${total} ${noun}`;
  return `${shown} ${noun}`;
});
const ROW_HEIGHT = 112;
const tableHeight = computed(() => {
  // Shorter than the first page of rows, so the table body scrolls and can load more.
  const visible = Math.min(Math.max(tableRows.value.length, 1), 6);
  return visible * ROW_HEIGHT + 48;
});

watch(filteredRows, () => {
  shownCount.value = PAGE_SIZE;
});

function onTableScroll(e: Event) {
  const el = e.target as HTMLElement | null;
  if (!el || !hasMoreModels.value) return;
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) {
    shownCount.value = Math.min(shownCount.value + PAGE_SIZE, filteredRows.value.length);
  }
}

function canEdit(row: ModelCatalogEntry): boolean {
  return (row.knobs?.length ?? 0) > 0 || Object.keys(row.contract ?? {}).length > 0;
}

const effectiveRuntime = computed(() => {
  const inf = status.value?.inference;
  if (!inf) return null;
  const isOnnx = inf.effective_summary === "onnx";
  return {
    summary: isOnnx ? "Downloaded files" : "Built-in guess",
    onnxCount: Object.values(inf.models).filter((v) => v === "onnx").length,
    heuristicCount: Object.values(inf.models).filter((v) => v === "heuristic").length,
    warnings: inf.warnings,
  };
});

const showGuessWarning = computed(() => {
  if (!status.value || !effectiveRuntime.value) return false;
  return effectiveRuntime.value.summary === "Built-in guess" && status.value.catalog.some((m) => m.on_disk);
});

const inferenceDirty = computed(
  () => status.value != null && inferenceDraft.value !== status.value.inference_backend,
);

function formatBytes(n: number | null | undefined): string {
  if (n == null || n <= 0) return "";
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n >= 10 * 1024 ? 0 : 1)} KB`;
  if (n < 1024 * 1024 * 1024) {
    const mb = n / (1024 * 1024);
    return `${mb >= 100 ? Math.round(mb) : mb.toFixed(1)} MB`;
  }
  const gb = n / (1024 * 1024 * 1024);
  return `${gb.toFixed(1)} GB`;
}

function statusText(row: ModelCatalogEntry): string {
  const size = formatBytes(diskBytes(row));
  if (row.on_disk) return size ? `Ready · ${size}` : "Ready";
  return size ? `Not downloaded · ${size}` : "Not downloaded";
}

function keptCount(row: ModelCatalogEntry): number {
  return row.enrollment_count ?? 0;
}

function canRemove(row: ModelCatalogEntry): boolean {
  return row.on_disk && keptCount(row) === 0;
}

function usageText(row: ModelCatalogEntry): string {
  const kept = keptCount(row);
  if (row.active && kept > 0) return "In use · matching saved enrollments";
  if (row.active) return "In use for new samples";
  if (kept > 0) return `Still matching ${kept} enrollment${kept === 1 ? "" : "s"}`;
  return statusText(row);
}

function usageClass(row: ModelCatalogEntry): string {
  if (row.active) return "is-active-copy";
  if (keptCount(row) > 0) return "is-kept-copy";
  return row.on_disk ? "is-ready" : "";
}

function enableLines(row: ModelCatalogEntry): string[] {
  const items = row.enables ?? [];
  if (items.length > 1 && items.every((item) => item.length <= 1)) return [items.join("")];
  return items;
}

function modelRowClass(row: ModelCatalogEntry): string {
  if (row.active) return "is-active-row";
  if (keptCount(row) > 0) return "is-kept-row";
  return "";
}

function applyStatus(next: ModelsStatusOut) {
  status.value = next;
  inferenceDraft.value = next.inference_backend;
  hardwareDraft.value = next.hardware.override ?? "auto";
  threadDraft.value = next.threads.value;
  if (settingsRow.value) {
    settingsRow.value = next.catalog.find((row) => row.key === settingsRow.value?.key) ?? null;
  }
  if (aboutRow.value) {
    aboutRow.value = next.catalog.find((row) => row.key === aboutRow.value?.key) ?? aboutRow.value;
  }
}

async function load() {
  loading.value = true;
  try {
    applyStatus(await api<ModelsStatusOut>("/v1/admin/models"));
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load models");
  } finally {
    loading.value = false;
  }
}

async function runDownload(keys?: string[], force = false) {
  downloading.value = true;
  if (keys?.length === 1) downloadingKey.value = keys[0];
  try {
    const res = await api<ModelDownloadResponse>("/v1/admin/models/download", {
      method: "POST",
      json: { keys: keys ?? null, force },
    });
    for (const r of res.results) {
      if (r.status === "downloaded") {
        message.success(`${r.key}: ${r.message}`);
      } else if (r.status === "skipped") {
        message.info(`${r.key}: ${r.message}`);
      }
    }
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Download failed");
  } finally {
    downloading.value = false;
    downloadingKey.value = null;
  }
}

function licenseLines(keys: string[]): string[] {
  const lines: string[] = [];
  for (const key of keys) {
    const row = catalogByKey.value.get(key);
    if (row?.license_warning) lines.push(`${modelTitle(row)} is ${row.license}`);
  }
  return lines;
}

function confirmThenDownload(keys: string[], force = false) {
  const lines = licenseLines(keys);
  if (!lines.length) {
    void runDownload(keys, force);
    return;
  }
  dialog.warning({
    title: "Check the license",
    content: `${lines.join(". ")}. Download only if that license works for you.`,
    positiveText: "Download",
    negativeText: "Cancel",
    onPositiveClick: () => runDownload(keys, force),
  });
}

function downloadSuggested() {
  const keys = suggestedMissing.value;
  if (!keys.length) return;
  confirmThenDownload(keys);
}

function downloadOne(key: string, force = false) {
  confirmThenDownload([key], force);
}

async function deleteOne(key: string) {
  deletingKey.value = key;
  try {
    const r = await api<{ key: string; status: string; message: string }>(
      `/v1/admin/models/${encodeURIComponent(key)}`,
      { method: "DELETE" },
    );
    message.success(r.message);
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Delete failed");
  } finally {
    deletingKey.value = null;
  }
}

async function reloadRuntime() {
  reloading.value = true;
  try {
    await api("/v1/admin/reload", { method: "POST" });
    message.success("Model runtime reloaded");
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Reload failed");
  } finally {
    reloading.value = false;
  }
}

async function saveInference() {
  savingInference.value = true;
  try {
    await api("/v1/admin/settings", {
      method: "PATCH",
      json: { inference_backend: inferenceDraft.value },
    });
    message.success("Saved");
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to save");
  } finally {
    savingInference.value = false;
  }
}

function openSettingsTab() {
  sectionTab.value = "settings";
}

function isCustom(row: ModelCatalogEntry): boolean {
  return row.origin === "custom";
}

function templateOnnx(category: string): Record<string, string | number> {
  const builtin = status.value?.catalog.find(
    (row) => row.category === category && row.origin !== "custom",
  );
  const onnx = builtin?.onnx ?? {};
  const copy: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(onnx)) {
    if (typeof value === "number" || typeof value === "string") copy[key] = value;
  }
  return copy;
}

function settingEntries(): { key: string; label: string; numeric: boolean }[] {
  return Object.keys(formOnnx.value).map((key) => ({
    key,
    label: settingLabels[key] || key,
    numeric: typeof formOnnx.value[key] === "number",
  }));
}

function openAddModel() {
  editingKey.value = null;
  formLabel.value = "";
  formCategory.value = status.value?.categories[0]?.id || "voice_match";
  formVersion.value = "";
  formUrl.value = "";
  formOnnx.value = templateOnnx(formCategory.value);
  showModelForm.value = true;
}

function onFormCategory(category: string) {
  formCategory.value = category;
  if (!editingKey.value) formOnnx.value = templateOnnx(category);
}

function openEditModel(row: ModelCatalogEntry) {
  editingKey.value = row.key;
  formLabel.value = modelTitle(row);
  formCategory.value = row.category;
  formVersion.value = row.version || "";
  formUrl.value = row.url;
  formOnnx.value = templateOnnx(row.category);
  for (const [key, value] of Object.entries(row.onnx ?? {})) {
    if (typeof value === "number" || typeof value === "string") formOnnx.value[key] = value;
  }
  showModelForm.value = true;
}

async function saveModel() {
  savingModel.value = true;
  try {
    const payload = {
      label: formLabel.value.trim(),
      version: formVersion.value.trim(),
      url: formUrl.value.trim(),
      onnx: formOnnx.value,
    };
    if (editingKey.value) {
      await api(`/v1/admin/models/custom/${encodeURIComponent(editingKey.value)}`, {
        method: "PATCH",
        json: payload,
      });
      message.success("Model updated. Re-download it if the file should change.");
    } else {
      await api("/v1/admin/models/custom", {
        method: "POST",
        json: { ...payload, category: formCategory.value },
      });
      message.success("Model added. Download it when you are ready.");
    }
    showModelForm.value = false;
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not save the model");
  } finally {
    savingModel.value = false;
  }
}

async function useModel(row: ModelCatalogEntry) {
  usingKey.value = row.key;
  try {
    await api("/v1/admin/models/active", {
      method: "POST",
      json: { category: row.category, key: row.key },
    });
    message.success(
      row.on_disk
        ? `${modelTitle(row)} is now in use`
        : `${modelTitle(row)} is selected. Download it before matching can use the file.`,
    );
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not switch models");
  } finally {
    usingKey.value = null;
  }
}

function requestUse(row: ModelCatalogEntry) {
  const count = row.reenroll_count ?? 0;
  if (count > 0) {
    dialog.warning({
      title: "Switch model",
      content: `${count} enrollment${count === 1 ? "" : "s"} still ${count === 1 ? "uses" : "use"} a different model. They keep matching with that model until you add samples for them here. That model stays until every enrollment has moved.`,
      positiveText: "Use for new samples",
      negativeText: "Cancel",
      onPositiveClick: () => useModel(row),
    });
    return;
  }
  void useModel(row);
}

async function saveHardware(value: string) {
  hardwareDraft.value = value;
  savingHardware.value = true;
  try {
    applyStatus(
      await api<ModelsStatusOut>("/v1/admin/models/hardware", {
        method: "PUT",
        json: { tier: value === "auto" ? null : value },
      }),
    );
    window.dispatchEvent(new Event("or-hardware-changed"));
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not update hardware");
    if (status.value) hardwareDraft.value = status.value.hardware.override ?? "auto";
  } finally {
    savingHardware.value = false;
  }
}

const threadDirty = computed(
  () => status.value != null && threadDraft.value != null && threadDraft.value !== status.value.threads.value,
);

async function saveThreads(reset = false) {
  savingThreads.value = true;
  try {
    await api("/v1/admin/settings", {
      method: "PATCH",
      json: { onnx_intra_op_threads: reset ? null : threadDraft.value },
    });
    message.success(reset ? "Thread count is automatic" : "Thread count saved");
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not save the thread count");
  } finally {
    savingThreads.value = false;
  }
}

function sameSetting(next: string | number | boolean | undefined, shipped: string | number | boolean): boolean {
  if (typeof shipped === "number") return Number(next) === shipped;
  return next === shipped;
}

function openSettings(row: ModelCatalogEntry) {
  settingsRow.value = row;
  const knobs: Record<string, number> = {};
  for (const knob of row.knobs ?? []) knobs[knob.key] = knob.value;
  knobDraft.value = knobs;
  const contract: Record<string, string | number | boolean> = {};
  for (const [key, shipped] of Object.entries(row.contract ?? {})) {
    const current = row.onnx?.[key];
    if (typeof current === "number" || typeof current === "string" || typeof current === "boolean") {
      contract[key] = current;
    } else if (typeof shipped === "number" || typeof shipped === "string" || typeof shipped === "boolean") {
      contract[key] = shipped;
    }
  }
  contractDraft.value = contract;
  showSettings.value = true;
}

async function saveKnobs() {
  const row = settingsRow.value;
  if (!row) return;
  savingKnobs.value = true;
  try {
    const overrides: Record<string, string | number | boolean | null> = {};
    for (const [key, shipped] of Object.entries(row.contract ?? {})) {
      if (typeof shipped !== "number" && typeof shipped !== "string" && typeof shipped !== "boolean") continue;
      const next = contractDraft.value[key];
      overrides[key] = sameSetting(next, shipped) ? null : (next ?? null);
    }
    for (const knob of row.knobs ?? []) {
      const next = knobDraft.value[knob.key];
      overrides[knob.key] = next === knob.default ? null : next;
    }
    applyStatus(
      await api<ModelsStatusOut>(`/v1/admin/models/${encodeURIComponent(row.key)}/settings`, {
        method: "PATCH",
        json: { overrides },
      }),
    );
    message.success("Settings saved");
    showSettings.value = false;
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not save settings");
  } finally {
    savingKnobs.value = false;
  }
}

async function resetKnobs() {
  const row = settingsRow.value;
  if (!row) return;
  savingKnobs.value = true;
  try {
    applyStatus(
      await api<ModelsStatusOut>(`/v1/admin/models/${encodeURIComponent(row.key)}/settings/reset`, {
        method: "POST",
      }),
    );
    const fresh = status.value?.catalog.find((item) => item.key === row.key);
    if (fresh) openSettings(fresh);
    message.success("Settings reset");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not reset settings");
  } finally {
    savingKnobs.value = false;
  }
}

const contractFields = computed(() => {
  const row = settingsRow.value;
  if (!row?.contract) return [];
  return Object.entries(row.contract)
    .filter((entry): entry is [string, string | number | boolean] => {
      const value = entry[1];
      return typeof value === "number" || typeof value === "string" || typeof value === "boolean";
    })
    .map(([key, shipped]) => ({
      key,
      label: settingLabels[key] || key,
      numeric: typeof shipped === "number",
      boolean: typeof shipped === "boolean",
    }));
});

function confirmRemove(row: ModelCatalogEntry) {
  dialog.warning({
    title: "Remove model",
    content: `Remove ${modelTitle(row)} from this server?`,
    positiveText: "Remove",
    negativeText: "Cancel",
    onPositiveClick: () => deleteOne(row.key),
  });
}

function modelMenu(row: ModelCatalogEntry): { label: string; key: string }[] {
  const items: { label: string; key: string }[] = [];
  if (!row.active) items.push({ label: "Use", key: "use" });
  if (row.on_disk) items.push({ label: "Re-download", key: "redownload" });
  else items.push({ label: "Download", key: "download" });
  if (isCustom(row)) {
    items.push({ label: "Details", key: "details" });
    items.push({ label: "Delete", key: "delete" });
  }
  if (canRemove(row)) items.push({ label: "Remove", key: "remove" });
  return items;
}

function iconAction(
  label: string,
  icon: Component,
  opts: { loading?: boolean; onClick?: () => void } = {},
) {
  return h(NTooltip, null, {
    trigger: () =>
      h(
        NButton,
        {
          quaternary: true,
          circle: true,
          size: "small",
          "aria-label": label,
          loading: opts.loading,
          onClick: opts.onClick,
        },
        { icon: () => h(NIcon, { size: 18 }, () => h(icon)) },
      ),
    default: () => label,
  });
}

function onModelMenu(row: ModelCatalogEntry, key: string) {
  if (key === "use") requestUse(row);
  else if (key === "download") downloadOne(row.key, false);
  else if (key === "redownload") downloadOne(row.key, true);
  else if (key === "details") openEditModel(row);
  else if (key === "delete") confirmDeleteModel(row);
  else if (key === "remove") confirmRemove(row);
}

function confirmDeleteModel(row: ModelCatalogEntry) {
  const kept = keptCount(row);
  if (kept > 0) {
    dialog.warning({
      title: "Model still in use",
      content: `${kept} enrollment${kept === 1 ? "" : "s"} still ${kept === 1 ? "matches" : "match"} with ${modelTitle(row)}. Add samples with the new model before deleting this one.`,
      positiveText: "OK",
    });
    return;
  }
  dialog.warning({
    title: "Delete model",
    content: `Delete ${modelTitle(row)} from the list? The downloaded file is removed too.`,
    positiveText: "Delete",
    negativeText: "Cancel",
    onPositiveClick: async () => {
      try {
        await api(`/v1/admin/models/custom/${encodeURIComponent(row.key)}`, { method: "DELETE" });
        message.success("Model deleted");
        await load();
      } catch (e) {
        message.error(e instanceof ApiError ? e.message : "Could not delete the model");
      }
    },
  });
}

const columns = computed<DataTableColumns<ModelCatalogEntry>>(() => [
  {
    title: "Model",
    key: "label",
    minWidth: 200,
    sorter: (a, b) => modelTitle(a).localeCompare(modelTitle(b)),
    render(row) {
      return h("div", { class: "model-cell" }, [
        h("div", { class: "name-line" }, [
          h("strong", modelTitle(row)),
          h(
            NTag,
            {
              size: "small",
              round: true,
              bordered: false,
              type: row.fit === "heavier" ? "warning" : "success",
            },
            () => fitText(row),
          ),
        ]),
        h("div", { class: ["usage-state", usageClass(row)] }, usageText(row)),
        h("div", { class: "cell-meta" }, row.use_for),
      ]);
    },
  },
  {
    title: "Category",
    key: "category",
    width: 124,
    sorter: (a, b) => categoryLabel(a.category).localeCompare(categoryLabel(b.category)),
    render(row) {
      return categoryLabel(row.category);
    },
  },
  {
    title: "Version",
    key: "version",
    minWidth: 168,
    sorter: (a, b) => (a.version || "").localeCompare(b.version || ""),
    render(row) {
      return h("span", { class: "version-cell" }, row.version || "—");
    },
  },
  {
    title: "Aimed at",
    key: "hardware",
    width: 128,
    render(row) {
      const note = fitLabel(row);
      return h("div", { class: "model-cell", title: row.hardware_note || undefined }, [
        h("div", machineLabel(row.hardware || "")),
        note ? h("div", { class: "cell-meta" }, note) : null,
        missingDeps(row).length
          ? h(
              "div",
              { class: "cell-warn" },
              `Also download ${missingDeps(row)
                .map((key) => catalogByKey.value.get(key)?.label || key)
                .join(", ")}.`,
            )
          : null,
      ]);
    },
  },
  {
    title: "Status",
    key: "on_disk",
    width: 210,
    render(row) {
      return h("div", [
        h("div", { class: row.on_disk ? "is-ready" : undefined }, statusText(row)),
        memoryLabel(row)
          ? h("div", { class: "cell-meta" }, `${memoryLabel(row)} system memory`)
          : null,
      ]);
    },
  },
  {
    title: "",
    key: "actions",
    width: 96,
    minWidth: 96,
    className: "actions-cell",
    render(row) {
      const menu = modelMenu(row);
      const actions: VNode[] = [];
      if (canEdit(row)) {
        actions.push(iconAction("Edit", CreateOutline, { onClick: () => openSettings(row) }));
      }
      if (menu.length) {
        actions.push(
          h(
            NDropdown,
            {
              options: menu,
              onSelect: (key: string) => onModelMenu(row, key),
            },
            {
              default: () =>
                h(
                  NButton,
                  {
                    quaternary: true,
                    circle: true,
                    size: "small",
                    "aria-label": `More actions for ${modelTitle(row)}`,
                    title: "More",
                    loading:
                      usingKey.value === row.key ||
                      downloadingKey.value === row.key ||
                      deletingKey.value === row.key,
                  },
                  { icon: () => h(NIcon, { size: 18 }, () => h(EllipsisHorizontalOutline)) },
                ),
            },
          ),
        );
      }
      return h("div", { class: "row-actions table-actions", onClick: (e: Event) => e.stopPropagation() }, actions);
    },
  },
]);

onMounted(() => {
  if (role.value !== "admin") {
    router.replace("/enrollments");
    return;
  }
  void load();
});
</script>

<template>
  <div class="or-page models-page">
    <PageHeader
      title="Models"
      description="Download a model for each kind of recognition. A heavier model in the same category can replace it later."
    >
      <template #tabs>
        <SegmentedControl
          v-model="sectionTab"
          aria-label="Model sections"
          :options="sectionTabs"
        />
      </template>
      <template #action>
        <NButton @click="openAddModel">Add a model</NButton>
        <NDropdown :options="[{ label: 'Reload models', key: 'reload' }]" @select="reloadRuntime">
          <NButton :loading="reloading">More</NButton>
        </NDropdown>
      </template>
    </PageHeader>

    <NSkeleton v-if="loading && !status" text :repeat="6" />

    <template v-else-if="status">
      <NAlert v-if="showGuessWarning && sectionTab !== 'settings'" type="warning" :bordered="false">
        <div class="guess-row">
          <span>Downloaded files are on this server, but matching is using the built-in guess.</span>
          <NButton text @click="openSettingsTab">Change</NButton>
        </div>
      </NAlert>

      <section v-if="sectionTab === 'recommended'" class="models-section">
        <div class="hardware-banner">
          <div>
            <strong>{{ status.hardware.label }}</strong>
            <p class="cell-meta">
              {{ status.hardware.cpu_count }} cores · {{ memoryText(status.hardware.memory_mb) }}
              <template v-if="status.hardware.override"> · override</template>
            </p>
          </div>
          <div class="hardware-actions">
            <NSelect
              class="hardware-select"
              :value="hardwareDraft"
              :options="hardwareOptions"
              :loading="savingHardware"
              @update:value="saveHardware"
            />
            <NButton
              v-if="suggestedMissing.length > 0"
              type="primary"
              :loading="downloading && !downloadingKey"
              @click="downloadSuggested"
            >
              <template #icon>
                <NIcon><CloudDownloadOutline /></NIcon>
              </template>
              Download suggested ({{ suggestedMissing.length }})
            </NButton>
          </div>
        </div>
        <p class="hint">
          One model for each kind of recognition, picked for this machine. A heavier model stays available under All models.
          <template v-if="suggestedPlan.disk > 0">
            Downloading every suggestion uses {{ formatBytes(suggestedPlan.disk) }} of disk.
            Loaded together, they need {{ memoryText(suggestedPlan.memory) }} of system memory.
            A heavier model in one category can sit next to a lighter model in another.
          </template>
        </p>
        <div class="recommend-grid">
          <article
            v-for="row in recommendedRows"
            :key="row.key"
            class="recommend-card is-clickable"
            :class="{ 'is-active': row.active, 'is-kept': !row.active && keptCount(row) > 0 }"
            @click="openAbout(row)"
          >
            <p class="recommend-kicker">{{ categoryLabel(row.category) }}</p>
            <div class="name-line">
              <strong>{{ modelTitle(row) }}</strong>
              <NTag size="small" round :bordered="false">Suggested</NTag>
              <NTag
                size="small"
                round
                :bordered="false"
                :type="row.fit === 'heavier' ? 'warning' : 'success'"
              >
                {{ fitText(row) }}
              </NTag>
            </div>
            <p class="usage-state" :class="usageClass(row)">{{ usageText(row) }}</p>
            <p class="hint">{{ row.use_for }}</p>
            <p v-if="formatBytes(diskBytes(row))" class="cell-meta">
              {{ formatBytes(diskBytes(row)) }} on disk
              <template v-if="memoryLabel(row)"> · {{ memoryLabel(row) }} system memory</template>
            </p>
            <div class="row-actions" @click.stop>
              <NButton v-if="!row.active" size="small" :loading="usingKey === row.key" @click="requestUse(row)">
                Use
              </NButton>
              <NButton
                size="small"
                :loading="downloadingKey === row.key"
                @click="downloadOne(row.key, row.on_disk)"
              >
                {{ row.on_disk ? "Re-download" : "Download" }}
              </NButton>
              <NButton v-if="canEdit(row)" size="small" @click="openSettings(row)">Edit</NButton>
            </div>
          </article>
        </div>
      </section>

      <section v-if="sectionTab === 'catalog'" class="models-section">
      <div class="toolbar">
        <NInput
          v-model:value="search"
          class="search-control"
          clearable
          placeholder="Search models"
        />
        <NSelect
          v-model:value="groupFilter"
          class="filter-control"
          :options="groupOptions"
          clearable
          placeholder="Category"
        />
        <NSelect
          v-model:value="statusFilter"
          class="filter-control"
          :options="statusOptions"
          clearable
          placeholder="Status"
        />
      </div>
      <p v-if="filteredRows.length === 0" class="filter-empty">
        Nothing matches.
        <NButton v-if="filtersActive" text type="primary" size="small" @click="clearFilters">
          Clear filters
        </NButton>
      </p>

      <template v-else>
        <div class="or-list-cards model-card-scroll" @scroll="onTableScroll">
          <article
            v-for="row in tableRows"
            :key="row.key"
            class="or-list-card model-card is-clickable"
            :class="{ 'is-active': row.active, 'is-kept': !row.active && keptCount(row) > 0 }"
            @click="openAbout(row)"
          >
            <div class="model-card-copy">
              <span class="or-list-card__title name-line">
                {{ modelTitle(row) }}
                <NTag
                  size="small"
                  round
                  :bordered="false"
                  :type="row.fit === 'heavier' ? 'warning' : 'success'"
                >
                  {{ fitText(row) }}
                </NTag>
              </span>
              <p class="usage-state" :class="usageClass(row)">{{ usageText(row) }}</p>
              <span class="or-list-card__meta">
                <span>{{ categoryLabel(row.category) }}</span>
                <span>{{ machineLabel(row.hardware || "") }}</span>
                <span v-if="fitLabel(row)">{{ fitLabel(row) }}</span>
                <span :class="{ 'is-ready': row.on_disk }">{{ statusText(row) }}</span>
              </span>
              <p class="meta-label">Version</p>
              <p class="cell-meta">{{ row.version || "—" }}</p>
              <p>{{ row.use_for }}</p>
            </div>
            <div class="row-actions" @click.stop>
              <NButton v-if="!row.active" size="small" :loading="usingKey === row.key" @click="requestUse(row)">
                Use
              </NButton>
              <NButton v-if="canEdit(row)" size="small" @click="openSettings(row)">Edit</NButton>
              <NButton
                size="small"
                :loading="downloadingKey === row.key"
                @click="downloadOne(row.key, row.on_disk)"
              >
                {{ row.on_disk ? "Re-download" : "Download" }}
              </NButton>
              <NButton v-if="isCustom(row)" size="small" quaternary @click="openEditModel(row)">Details</NButton>
              <NButton v-if="isCustom(row)" size="small" quaternary @click="confirmDeleteModel(row)">
                Delete
              </NButton>
              <NPopconfirm v-if="canRemove(row)" @positive-click="deleteOne(row.key)">
                <template #trigger>
                  <NButton size="small" quaternary :loading="deletingKey === row.key">Remove</NButton>
                </template>
                Remove {{ modelTitle(row) }} from this server?
              </NPopconfirm>
            </div>
          </article>
        </div>
        <div
          class="or-table-wrap or-table-desktop models-table"
          :style="{ height: `${tableHeight}px` }"
          @scroll.capture="onTableScroll"
        >
          <NDataTable
            :columns="columns"
            :data="tableRows"
            :bordered="false"
            flex-height
            virtual-scroll
            :header-height="44"
            :min-row-height="ROW_HEIGHT"
            :row-class-name="modelRowClass"
            :row-props="modelRowProps"
            size="medium"
            :row-key="(row: ModelCatalogEntry) => row.key"
          />
        </div>
        <p class="table-total">
          {{ modelCountLabel }}
          <template v-if="hasMoreModels"> · scroll for more</template>
        </p>
      </template>
      </section>

      <section v-if="sectionTab === 'settings'" class="models-section">
        <h3 class="subhead">Categories</h3>
        <p class="hint">
          Each kind of recognition needs its own model. Download one file for a category and it can do that job.
        </p>
        <div class="recommend-grid">
          <article
            v-for="card in categoryCards"
            :key="card.id"
            class="recommend-card"
            :class="{ 'is-active': card.downloaded }"
          >
            <p class="recommend-kicker">{{ card.label }}</p>
            <p class="usage-state" :class="{ 'is-active-copy': card.downloaded }">
              {{ categoryStatus(card) }}
            </p>
            <p class="hint">{{ card.summary }}</p>
            <p v-if="card.benefit" class="cell-meta">{{ card.benefit }}</p>
            <div class="row-actions">
              <NButton size="small" @click="showCategory(card.id)">See models</NButton>
            </div>
          </article>
        </div>

        <h3 class="subhead">How matching runs</h3>
        <p class="hint">
          Automatic uses a downloaded file when you have one, and a simple built-in guess when you do not.
        </p>
        <div class="inference-controls">
          <NSelect v-model:value="inferenceDraft" :options="inferenceOptions" />
          <NButton :loading="savingInference" :disabled="!inferenceDirty" @click="saveInference">
            Save
          </NButton>
        </div>
        <p v-if="effectiveRuntime" class="hint runtime-line">
          Right now: {{ effectiveRuntime.summary }}.
          <template v-if="status.inference_backend === 'auto'">
            {{ effectiveRuntime.onnxCount }} of
            {{ effectiveRuntime.onnxCount + effectiveRuntime.heuristicCount }}
            jobs use a downloaded file.
          </template>
        </p>
        <NAlert
          v-if="effectiveRuntime?.warnings?.length"
          type="warning"
          :bordered="false"
          class="warn-alert"
        >
          <ul class="warn-list">
            <li v-for="(w, i) in effectiveRuntime.warnings" :key="i">{{ w }}</li>
          </ul>
        </NAlert>

        <h3 class="subhead">How hard the files work</h3>
        <p class="hint">
          Automatic uses up to four CPU cores. Set a number from 1 to 8 when this machine should work harder or leave more room for other programs.
        </p>
        <div class="inference-controls">
          <NInputNumber v-model:value="threadDraft" :min="1" :max="8" :step="1" />
          <NButton :loading="savingThreads" :disabled="!threadDirty" @click="saveThreads()">Save</NButton>
          <NButton
            v-if="status.threads.overridden"
            :loading="savingThreads"
            @click="saveThreads(true)"
          >
            Automatic ({{ status.threads.automatic }})
          </NButton>
        </div>

        <h3 class="subhead">Where these files are stored</h3>
        <p class="hint">New downloads go in this folder. Edit a model to change how its file runs.</p>
        <p class="cell-meta">{{ status.models_dir }}</p>
      </section>

      <NModal
        v-model:show="showModelForm"
        preset="card"
        :title="editingKey ? 'Edit model' : 'Add a model'"
        class="or-modal"
      >
        <NForm label-placement="top">
          <NFormItem label="Name" required>
            <NInput v-model:value="formLabel" placeholder="Community voice model" />
          </NFormItem>
          <NFormItem label="Category" required>
            <NSelect
              :value="formCategory"
              :options="groupOptions"
              :disabled="editingKey != null"
              @update:value="onFormCategory"
            />
          </NFormItem>
          <p class="hint">
            Your file should work like the other models in this category. Saved samples keep the version below. Change the version when you replace the file, then re-download.
          </p>
          <NFormItem label="Version" required>
            <NInput v-model:value="formVersion" placeholder="my-voice-v1" />
          </NFormItem>
          <NFormItem label="Download link" required>
            <NInput v-model:value="formUrl" placeholder="https://example.com/model.onnx" />
          </NFormItem>
          <template v-if="settingEntries().length">
            <h3 class="subhead">Recommended settings</h3>
            <p class="hint">These match this category. Change a number only when your file needs a different size.</p>
            <NFormItem v-for="field in settingEntries()" :key="field.key" :label="field.label">
              <NInputNumber
                v-if="field.numeric"
                :value="Number(formOnnx[field.key])"
                class="setting-input"
                @update:value="(value) => (formOnnx[field.key] = value ?? 0)"
              />
              <NInput v-else v-model:value="formOnnx[field.key] as string" />
            </NFormItem>
          </template>
        </NForm>
        <template #footer>
          <div class="or-modal-footer">
            <NButton @click="showModelForm = false">Cancel</NButton>
            <NButton
              type="primary"
              :loading="savingModel"
              :disabled="!formLabel.trim() || !formVersion.trim() || !formUrl.trim()"
              @click="saveModel"
            >
              {{ editingKey ? "Save" : "Add" }}
            </NButton>
          </div>
        </template>
      </NModal>

      <NModal
        v-model:show="showAbout"
        preset="card"
        class="or-modal about-modal"
        :style="{ width: 'min(96vw, 1180px)' }"
      >
        <template #header>
          <div v-if="displayRow" class="product-header">
            <span>{{ modelTitle(displayRow) }}</span>
            <NTag
              round
              :bordered="false"
              :type="displayRow.fit === 'heavier' ? 'warning' : 'success'"
            >
              {{ fitText(displayRow) }}
            </NTag>
          </div>
        </template>
        <div v-if="aboutRow && displayRow" class="product">
          <SegmentedControl
            v-if="otherMates.length"
            v-model="aboutTab"
            :options="aboutTabs"
            aria-label="Model"
          />

          <div v-if="aboutTab === 'others'" class="about-mates">
            <button
              v-for="mate in otherMates"
              :key="mate.key"
              type="button"
              class="about-mate"
              :class="{ 'is-picked': mate.key === pickedKey }"
              @click="selectMate(mate)"
            >
              <span>
                <strong>{{ modelTitle(mate) }}</strong>
                <em>{{ machineLabel(mate.hardware || "") }}</em>
              </span>
              <span class="about-mate-flag">
                <template v-if="mate.suggested">Suggested</template>
                <template v-else-if="mate.fit === 'heavier'">Too heavy</template>
                <template v-else-if="mate.on_disk">Ready</template>
              </span>
            </button>
          </div>

          <div v-if="aboutTab === 'overview' || pickedMate" class="product-sheet">
            <div class="product-copy">
              <div class="about-kicker">
                <NTag size="small" round :bordered="false">{{ categoryLabel(displayRow.category) }}</NTag>
                <NTag v-if="displayRow.suggested" size="small" round :bordered="false">Suggested</NTag>
                <NTag v-if="displayRow.active" size="small" round :bordered="false" type="success">In use</NTag>
              </div>
              <p class="about-body">{{ displayRow.description }}</p>
              <div class="product-actions">
                <NButton
                  v-if="!displayRow.active"
                  size="small"
                  :loading="usingKey === displayRow.key"
                  @click="requestUse(displayRow)"
                >
                  Use
                </NButton>
                <NButton
                  type="primary"
                  size="small"
                  :loading="downloadingKey === displayRow.key"
                  @click="downloadOne(displayRow.key, displayRow.on_disk)"
                >
                  {{ displayRow.on_disk ? "Re-download" : "Download" }}
                </NButton>
                <a
                  v-if="displayRow.page_url"
                  class="about-link"
                  :href="displayRow.page_url"
                  target="_blank"
                  rel="noreferrer"
                >
                  Learn more
                </a>
              </div>
            </div>
            <dl class="product-specs">
              <div>
                <dt>Disk space</dt>
                <dd>{{ formatBytes(diskBytes(displayRow)) || "—" }}</dd>
              </div>
              <div>
                <dt>System memory</dt>
                <dd>{{ memoryLabel(displayRow) || "—" }}</dd>
              </div>
              <div>
                <dt>Aimed at</dt>
                <dd>{{ machineLabel(displayRow.hardware || "") }}</dd>
              </div>
              <div>
                <dt>License</dt>
                <dd>{{ displayRow.license || "—" }}</dd>
              </div>
              <div class="is-wide">
                <dt>Version</dt>
                <dd>{{ displayRow.version || "—" }}</dd>
              </div>
            </dl>
          </div>
        </div>
      </NModal>

      <NModal v-model:show="showSettings" preset="card" title="ONNX settings" class="or-modal">
        <template v-if="settingsRow">
          <p class="hint">{{ modelTitle(settingsRow) }}. These values are applied the next time this model runs.</p>
          <NForm label-placement="top">
            <NFormItem v-for="field in contractFields" :key="field.key" :label="field.label">
              <NInputNumber
                v-if="field.numeric"
                :value="Number(contractDraft[field.key])"
                class="setting-input"
                @update:value="(value) => (contractDraft[field.key] = value ?? 0)"
              />
              <NInput v-else v-model:value="contractDraft[field.key] as string" />
            </NFormItem>
            <NFormItem v-for="knob in settingsRow.knobs ?? []" :key="knob.key" :label="knob.label">
              <NInputNumber
                v-model:value="knobDraft[knob.key]"
                class="setting-input"
                :min="knob.min"
                :max="knob.max"
                :step="knob.step"
              />
            </NFormItem>
          </NForm>
        </template>
        <template #footer>
          <div class="or-modal-footer">
            <NButton :loading="savingKnobs" @click="resetKnobs">Reset</NButton>
            <NButton @click="showSettings = false">Cancel</NButton>
            <NButton type="primary" :loading="savingKnobs" @click="saveKnobs">Save</NButton>
          </div>
        </template>
      </NModal>
    </template>
  </div>
</template>

<style scoped>
.hardware-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px 16px;
}

.hardware-banner strong {
  font-size: 1rem;
}

.hardware-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.hardware-select {
  width: 240px;
  max-width: 100%;
}

.models-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.recommend-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.recommend-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  height: 100%;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid var(--or-line, var(--n-border-color));
  border-radius: var(--or-radius-md, 10px);
  background: var(--or-surface, transparent);
}

.recommend-card.is-active {
  border-color: color-mix(in oklab, var(--or-success) 55%, var(--or-line));
}

.recommend-card.is-kept {
  border-color: color-mix(in oklab, var(--or-warning) 55%, var(--or-line));
}

.recommend-card .row-actions {
  margin-top: auto;
}

.about-modal {
  width: min(96vw, 1180px) !important;
  max-width: 1180px;
}

.product-header {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.product-header span {
  min-width: 0;
}

.about-modal :deep(.n-card__content) {
  padding-top: 8px;
}

.product {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.product-sheet {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.product-copy {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.product-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.about-kicker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.about-body {
  margin: 0;
  max-width: 68ch;
  font-size: 1.05rem;
  line-height: 1.6;
}

.product-specs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 0;
}

.product-specs div {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  min-height: 78px;
  padding: 16px 18px;
  border: 1px solid var(--or-line, var(--n-border-color));
  border-radius: var(--or-radius-md, 10px);
}

.product-specs .is-wide {
  grid-column: span 2;
}

.product-specs dt {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--n-text-color-3);
}

.product-specs dd {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 600;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.about-mates {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.about-mate {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-height: 96px;
  padding: 12px;
  text-align: left;
  color: inherit;
  background: transparent;
  border: 1px solid var(--or-line, var(--n-border-color));
  border-radius: var(--or-radius-md, 10px);
  cursor: pointer;
}

.about-mate.is-picked {
  border-color: var(--or-accent, var(--n-primary-color));
}

.about-mate em {
  display: block;
  margin-top: 4px;
  font-style: normal;
  font-size: 0.8rem;
  line-height: 1.4;
  color: var(--n-text-color-3);
}

.about-mate-flag {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--n-text-color-3);
}

.about-link {
  color: var(--or-accent, var(--n-primary-color));
  font-weight: 600;
}

.is-clickable {
  cursor: pointer;
}

@media (max-width: 720px) {
  .product-specs,
  .about-mates {
    grid-template-columns: 1fr;
  }

  .product-specs .is-wide {
    grid-column: auto;
  }
}

.usage-state {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
}

.usage-state.is-active-copy {
  color: var(--or-success);
}

.usage-state.is-kept-copy {
  color: var(--or-warning);
}

.meta-label {
  margin: 4px 0 0;
  font-size: 0.75rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--n-text-color-3);
}

.recommend-kicker {
  margin: 0;
  font-size: 0.75rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--n-text-color-3);
}

.models-table :deep(.n-data-table) {
  height: 100%;
}

.models-table :deep(.n-data-table-td) {
  vertical-align: top;
}

.models-table :deep(.actions-cell) {
  vertical-align: middle;
  width: 96px;
}

.models-table :deep(.table-actions) {
  width: 100%;
  flex-wrap: nowrap;
  justify-content: flex-end;
  gap: 2px;
}

.models-table :deep(.table-actions > *) {
  flex: none;
  width: auto;
}

.models-table :deep(.table-actions > :first-child) {
  margin-left: auto;
}

.models-table :deep(.table-actions .n-button) {
  width: 28px;
  min-width: 28px;
  height: 28px;
}

.models-table :deep(.is-active-row .n-data-table-td:first-child) {
  box-shadow: inset 3px 0 0 var(--or-success);
}

.models-table :deep(.is-kept-row .n-data-table-td:first-child) {
  box-shadow: inset 3px 0 0 var(--or-warning);
}

.models-page :deep(.model-cell) {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-width: 0;
}

.models-page :deep(.version-cell) {
  overflow-wrap: anywhere;
  font-size: 0.8125rem;
  line-height: 1.35;
}

.model-card.is-active {
  border-color: color-mix(in oklab, var(--or-success) 55%, var(--or-line));
}

.model-card.is-kept {
  border-color: color-mix(in oklab, var(--or-warning) 55%, var(--or-line));
}

.model-card .row-actions {
  margin-top: auto;
}

.model-card .meta-label {
  margin-top: 6px;
}

.model-card-scroll {
  max-height: 70vh;
  overflow: auto;
}

.contract-line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 4px 0 0;
  font-size: 0.875rem;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--or-inline-gap);
}

.search-control {
  width: 240px;
  max-width: 100%;
}

.filter-control {
  width: 200px;
  max-width: 100%;
}

.hint,
.cell-meta,
.table-total,
.filter-empty {
  margin: 0;
  color: var(--n-text-color-3);
  font-size: 0.875rem;
  line-height: 1.45;
}

.filter-empty {
  text-align: center;
}

.table-total {
  font-size: 0.8125rem;
}

.model-card {
  cursor: default;
}

.model-card:hover {
  border-color: var(--or-line, var(--n-border-color));
}

.model-card-copy p {
  margin: 4px 0 0;
  color: var(--n-text-color-3);
  font-size: 0.875rem;
}

.models-page :deep(.name-cell) {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.models-page :deep(.name-line) {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.models-page :deep(.cell-meta) {
  color: var(--n-text-color-3);
  font-size: 0.8125rem;
}

.models-page :deep(.cell-warn) {
  color: var(--n-warning-color);
  font-size: 0.8125rem;
}

.models-page :deep(.is-ready),
.is-ready {
  color: var(--n-success-color);
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.guess-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
}

.subhead {
  margin: 16px 0 0;
  font-size: 0.9375rem;
  font-weight: 600;
}

.subhead:first-child {
  margin-top: 0;
}

.inference-controls {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 12px;
  max-width: 28rem;
}

.inference-controls :deep(.n-select) {
  flex: 1;
  min-width: 0;
}

.setting-input {
  width: 100%;
}

.runtime-line {
  margin-top: 10px;
}

.warn-alert {
  margin-top: 12px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.warn-list {
  margin: 0;
  padding-left: 1.1rem;
}

@media (max-width: 720px) {
  .search-control,
  .filter-control,
  .hardware-select,
  .inference-controls {
    width: 100%;
  }

  .inference-controls {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
