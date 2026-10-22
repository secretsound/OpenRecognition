<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import {
  NButton,
  NCheckbox,
  NDataTable,
  NForm,
  NFormItem,
  NIcon,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSwitch,
  useMessage,
} from "naive-ui";
import type { DataTableColumns, FormInst } from "naive-ui";
import { AddOutline, LinkOutline } from "@vicons/ionicons5";
import { api } from "@/api/client";
import type { WebhookSubscriptionOut } from "@/types/api";
import EmptyState from "@/components/EmptyState.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import DataList from "@/components/kit/DataList.vue";
import Chip from "@/components/kit/Chip.vue";
import TimeAgo from "@/components/kit/TimeAgo.vue";
import { ApiError } from "@/api/client";
import {
  WEBHOOK_DEFAULT_MESSAGE,
  WEBHOOK_DEFAULT_TITLE,
  WEBHOOK_EVENTS,
  WEBHOOK_PREVIEW_CONTEXT,
  WEBHOOK_PREVIEW_DETAILS,
  WEBHOOK_VARIABLES,
  renderWebhookTemplate,
  webhookEventLabel,
} from "@/constants/webhookVariables";
import "./integration-panel.css";

type WebhookForm = {
  name: string;
  url: string;
  events: string[];
  debounce_seconds: number | null;
  title_template: string;
  message_template: string;
  include_details: boolean;
};

const emptyForm = (): WebhookForm => ({
  name: "",
  url: "",
  events: ["recognition.match", "recognition.unknown"],
  debounce_seconds: 30,
  title_template: WEBHOOK_DEFAULT_TITLE,
  message_template: WEBHOOK_DEFAULT_MESSAGE,
  include_details: true,
});

const message = useMessage();
const loading = ref(true);
const rows = ref<WebhookSubscriptionOut[]>([]);
const showEditor = ref(false);
const saving = ref(false);
const formRef = ref<FormInst | null>(null);
const form = ref<WebhookForm>(emptyForm());
const editingId = ref<string | null>(null);
const lastField = ref<"title" | "message">("title");

const isEditing = computed(() => editingId.value !== null);

function hostFromUrl(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.host + (parsed.pathname === "/" ? "" : parsed.pathname);
  } catch {
    return url;
  }
}

function displayName(row: WebhookSubscriptionOut): string {
  return row.name.trim() || hostFromUrl(row.url);
}

function toggleEvent(event: string, on: boolean) {
  const current = new Set(form.value.events);
  if (on) current.add(event);
  else current.delete(event);
  form.value.events = WEBHOOK_EVENTS.map((item) => item.value).filter((value) => current.has(value));
}

function variableToken(key: string) {
  return `{{${key}}}`;
}

function insertVariable(key: string) {
  const token = variableToken(key);
  const field = lastField.value === "title" ? "title_template" : "message_template";
  const current = form.value[field];
  form.value[field] = current
    ? current.endsWith(" ") || current.endsWith("{")
      ? `${current}${token}`
      : `${current} ${token}`
    : token;
}

const previewTitle = computed(() =>
  renderWebhookTemplate(form.value.title_template, WEBHOOK_PREVIEW_CONTEXT),
);
const previewMessage = computed(() =>
  renderWebhookTemplate(form.value.message_template, WEBHOOK_PREVIEW_CONTEXT),
);
const previewJson = computed(() => {
  const body: Record<string, unknown> = {
    title: previewTitle.value,
    message: previewMessage.value,
    event: "recognition.match",
  };
  if (form.value.include_details) {
    body.details = WEBHOOK_PREVIEW_DETAILS;
  }
  return JSON.stringify(body, null, 2);
});

const columns: DataTableColumns<WebhookSubscriptionOut> = [
  {
    title: "Name",
    key: "name",
    minWidth: 160,
    ellipsis: { tooltip: true },
    sorter: (a, b) => displayName(a).localeCompare(displayName(b)),
    render(row) {
      return h("span", { class: "wh-name" }, displayName(row));
    },
  },
  {
    title: "Address",
    key: "url",
    minWidth: 200,
    ellipsis: { tooltip: true },
    render(row) {
      return h("span", { class: "or-muted" }, hostFromUrl(row.url));
    },
  },
  {
    title: "Sends when",
    key: "events",
    minWidth: 200,
    render(row) {
      return h(
        "span",
        { class: "wh-chips" },
        row.events.map((event) => h(Chip, { key: event }, () => webhookEventLabel(event))),
      );
    },
  },
  {
    title: "Wait",
    key: "debounce_seconds",
    width: 88,
    render(row) {
      return `${row.debounce_seconds}s`;
    },
  },
  {
    title: "Added",
    key: "created_at",
    width: 120,
    render(row) {
      return h(TimeAgo, { value: row.created_at });
    },
  },
];

function rowProps(row: WebhookSubscriptionOut) {
  return {
    style: "cursor: pointer",
    onClick: () => openEditor(row),
  };
}

function openCreate() {
  editingId.value = null;
  form.value = emptyForm();
  lastField.value = "title";
  showEditor.value = true;
}

function openEditor(row: WebhookSubscriptionOut) {
  editingId.value = row.id;
  form.value = {
    name: row.name ?? "",
    url: row.url,
    events: row.events.length ? [...row.events] : ["recognition.match"],
    debounce_seconds: row.debounce_seconds,
    title_template: row.title_template || WEBHOOK_DEFAULT_TITLE,
    message_template: row.message_template || WEBHOOK_DEFAULT_MESSAGE,
    include_details: row.include_details !== false,
  };
  lastField.value = "title";
  showEditor.value = true;
}

async function load() {
  loading.value = true;
  try {
    rows.value = await api<WebhookSubscriptionOut[]>("/v1/integrations/webhooks");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load webhooks");
  } finally {
    loading.value = false;
  }
}

async function save() {
  await formRef.value?.validate();
  if (!form.value.events.length) {
    message.error("Choose at least one event");
    return;
  }
  saving.value = true;
  const payload = {
    name: form.value.name.trim(),
    url: form.value.url.trim(),
    events: form.value.events,
    debounce_seconds: form.value.debounce_seconds ?? 30,
    title_template: form.value.title_template,
    message_template: form.value.message_template,
    include_details: form.value.include_details,
    filters: {},
  };
  try {
    if (editingId.value) {
      await api(`/v1/integrations/webhooks/${editingId.value}`, {
        method: "PATCH",
        json: payload,
      });
      message.success("Webhook saved");
    } else {
      await api("/v1/integrations/webhooks", {
        method: "POST",
        json: payload,
      });
      message.success("Webhook added");
    }
    showEditor.value = false;
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to save webhook");
  } finally {
    saving.value = false;
  }
}

async function remove() {
  if (!editingId.value) return;
  try {
    await api(`/v1/integrations/webhooks/${editingId.value}`, { method: "DELETE" });
    message.success("Webhook removed");
    showEditor.value = false;
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to remove webhook");
  }
}

onMounted(load);
</script>

<template>
  <div class="int-panel">
    <header class="int-panel__header">
      <p class="int-panel__lead">
        Send a JSON message when someone is recognized. Write a title and body with
        variables from the event, then click a row to change it later.
      </p>
      <NButton v-if="rows.length" type="primary" @click="openCreate">
        <template #icon>
          <NIcon><AddOutline /></NIcon>
        </template>
        Add webhook
      </NButton>
    </header>

    <ContentSkeleton v-if="loading && !rows.length" variant="table" />
    <EmptyState
      v-else-if="!loading && rows.length === 0"
      title="No webhooks yet"
      description="Point Home Assistant, Node-RED, or any web address at your recognition events."
      :icon="LinkOutline"
      action-label="Add webhook"
      @action="openCreate"
    />
    <template v-else>
      <DataList :items="rows" :get-key="(row) => row.id">
        <template #table>
          <div class="or-table-wrap">
            <NDataTable
              :columns="columns"
              :data="rows"
              :loading="loading"
              :bordered="false"
              size="medium"
              :row-key="(row: WebhookSubscriptionOut) => row.id"
              :row-props="rowProps"
            />
          </div>
        </template>
        <template #card="{ item }">
          <div class="or-list-card" role="button" tabindex="0" @click="openEditor(item)">
            <span class="or-list-card__title">{{ displayName(item) }}</span>
            <span class="or-list-card__meta">
              <Chip v-for="event in item.events" :key="event">{{ webhookEventLabel(event) }}</Chip>
              <span>Waits {{ item.debounce_seconds }}s</span>
            </span>
          </div>
        </template>
      </DataList>
      <p class="or-footer-count">
        {{ rows.length }} webhook{{ rows.length === 1 ? "" : "s" }}
      </p>
    </template>

    <NModal
      v-model:show="showEditor"
      preset="card"
      :title="isEditing ? 'Edit webhook' : 'Add webhook'"
      class="or-modal or-modal--wide or-modal--webhook"
    >
      <NForm ref="formRef" :model="form" label-placement="top">
        <div class="wh-editor">
          <div class="wh-editor__form">
            <NFormItem label="Name" path="name">
              <NInput v-model:value="form.name" placeholder="Kitchen lights" maxlength="80" />
            </NFormItem>
            <NFormItem
              label="Web address"
              path="url"
              :rule="{ required: true, message: 'A web address is required' }"
            >
              <NInput
                v-model:value="form.url"
                placeholder="https://homeassistant.local:8123/api/webhook/..."
              />
            </NFormItem>
            <NFormItem label="Send when">
              <div class="wh-events">
                <label v-for="opt in WEBHOOK_EVENTS" :key="opt.value" class="wh-event">
                  <NCheckbox
                    :checked="form.events.includes(opt.value)"
                    @update:checked="(on: boolean) => toggleEvent(opt.value, on)"
                  />
                  <span class="wh-event__copy">
                    <span class="wh-event__label">{{ opt.label }}</span>
                    <span class="wh-event__hint">{{ opt.hint }}</span>
                  </span>
                </label>
              </div>
            </NFormItem>
            <NFormItem label="Title">
              <NInput
                v-model:value="form.title_template"
                placeholder="{{label}} was recognized"
                maxlength="500"
                @focus="lastField = 'title'"
              />
            </NFormItem>
            <NFormItem label="Message">
              <NInput
                v-model:value="form.message_template"
                type="textarea"
                :autosize="{ minRows: 3, maxRows: 6 }"
                placeholder="{{label}} matched at {{confidence}} on {{modality}}"
                maxlength="2000"
                @focus="lastField = 'message'"
              />
            </NFormItem>
            <NFormItem label="Wait before repeating">
              <NInputNumber
                v-model:value="form.debounce_seconds"
                :min="0"
                :max="3600"
                style="width: 100%"
              />
              <p class="conn-field__hint">Seconds to wait before sending the same person again.</p>
            </NFormItem>
            <div class="conn-switch">
              <div class="conn-switch__copy">
                <span class="conn-switch__label">Include extra details</span>
                <p class="conn-switch__hint">
                  Adds mode, confidence, scores, camera, and other fields under
                  <code>details</code> in the JSON body.
                </p>
              </div>
              <NSwitch v-model:value="form.include_details" />
            </div>
          </div>
          <aside class="wh-aside">
            <h3 class="wh-aside__title">Variables</h3>
            <p class="wh-aside__lead">
              Click to insert into the {{ lastField === "title" ? "title" : "message" }}.
            </p>
            <ul class="wh-vars">
              <li v-for="item in WEBHOOK_VARIABLES" :key="item.key">
                <button type="button" class="wh-var" @click="insertVariable(item.key)">
                  <code>{{ variableToken(item.key) }}</code>
                  <span>{{ item.hint }}</span>
                </button>
              </li>
            </ul>
          </aside>
          <aside class="wh-aside wh-aside--example">
            <h3 class="wh-aside__title">Example</h3>
            <p class="wh-aside__lead">How this looks when Alex is recognized.</p>
            <p class="wh-preview__title">{{ previewTitle || "—" }}</p>
            <p class="wh-preview__message">{{ previewMessage || "—" }}</p>
            <pre class="wh-json">{{ previewJson }}</pre>
          </aside>
        </div>
      </NForm>
      <template #footer>
        <div class="or-modal-footer" :class="{ 'or-modal-footer--split': isEditing }">
          <NPopconfirm v-if="isEditing" @positive-click="remove">
            <template #trigger>
              <NButton type="error" secondary>Remove</NButton>
            </template>
            Remove this webhook?
          </NPopconfirm>
          <div class="or-modal-footer__actions">
            <NButton @click="showEditor = false">Cancel</NButton>
            <NButton type="primary" :loading="saving" @click="save">
              {{ isEditing ? "Save" : "Add" }}
            </NButton>
          </div>
        </div>
      </template>
    </NModal>
  </div>
</template>
