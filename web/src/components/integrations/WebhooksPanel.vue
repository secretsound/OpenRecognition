<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  NButton,
  NModal,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSkeleton,
  NPopconfirm,
  NIcon,
  NTag,
  useMessage,
} from "naive-ui";
import type { FormInst } from "naive-ui";
import { AddOutline, LinkOutline } from "@vicons/ionicons5";
import { api } from "@/api/client";
import type { WebhookSubscriptionOut } from "@/types/api";
import EmptyState from "@/components/EmptyState.vue";
import { ApiError } from "@/api/client";
import "./integration-panel.css";

const message = useMessage();
const loading = ref(true);
const rows = ref<WebhookSubscriptionOut[]>([]);
const showCreate = ref(false);
const creating = ref(false);
const formRef = ref<FormInst | null>(null);
const form = ref({ url: "", debounce_seconds: 30 });

function eventLabel(event: string) {
  if (event === "recognition.match") return "Someone matched";
  if (event === "recognition.unknown") return "Nobody matched";
  return event.replace(/^recognition\./, "").replace(/_/g, " ");
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

async function create() {
  await formRef.value?.validate();
  creating.value = true;
  try {
    await api("/v1/integrations/webhooks", {
      method: "POST",
      json: {
        url: form.value.url,
        debounce_seconds: form.value.debounce_seconds,
        events: ["recognition.match", "recognition.unknown"],
        filters: {},
      },
    });
    message.success("Webhook added");
    showCreate.value = false;
    form.value = { url: "", debounce_seconds: 30 };
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to add webhook");
  } finally {
    creating.value = false;
  }
}

async function remove(id: string) {
  try {
    await api(`/v1/integrations/webhooks/${id}`, { method: "DELETE" });
    message.success("Webhook removed");
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
        OpenRecognition sends a request to each address when someone is recognized, or when
        nobody matches. Repeated events are combined so you are not notified twice.
      </p>
      <NButton type="primary" @click="showCreate = true">
        <template #icon>
          <NIcon><AddOutline /></NIcon>
        </template>
        Add webhook
      </NButton>
    </header>

    <NSkeleton v-if="loading" text :repeat="4" />
    <EmptyState
      v-else-if="rows.length === 0"
      title="No webhooks yet"
      description="Point Home Assistant, Node-RED, or any web address at your recognition events."
      :icon="LinkOutline"
      action-label="Add webhook"
      @action="showCreate = true"
    />
    <section v-else class="conn-block">
      <ul class="conn-list">
        <li v-for="row in rows" :key="row.id" class="conn-list__item">
          <div>
            <div class="conn-list__title">{{ row.url }}</div>
            <div class="conn-list__meta">
              <NTag
                v-for="event in row.events"
                :key="event"
                size="small"
                round
                :bordered="false"
              >
                {{ eventLabel(event) }}
              </NTag>
              <span>Waits {{ row.debounce_seconds }}s before repeating</span>
            </div>
          </div>
          <NPopconfirm @positive-click="remove(row.id)">
            <template #trigger>
              <NButton quaternary type="error">Remove</NButton>
            </template>
            Remove this webhook?
          </NPopconfirm>
        </li>
      </ul>
    </section>

    <NModal v-model:show="showCreate" preset="card" title="Add webhook" class="or-modal or-modal--narrow">
      <NForm ref="formRef" :model="form" label-placement="top">
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
        <NFormItem label="Wait before repeating">
          <NInputNumber
            v-model:value="form.debounce_seconds"
            :min="0"
            :max="3600"
            style="width: 100%"
          />
          <p class="conn-field__hint">Seconds to wait before sending the same event again.</p>
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="or-modal-footer">
          <NButton @click="showCreate = false">Cancel</NButton>
          <NButton type="primary" :loading="creating" @click="create">Add</NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>

