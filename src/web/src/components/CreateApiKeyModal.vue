<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NModal, NForm, NFormItem, NInput, NCheckbox, NButton, NPopconfirm, useMessage } from "naive-ui";
import type { FormInst } from "naive-ui";
import { api, ApiError } from "@/api/client";
import type { ApiKeyCreated, ApiKeyOut } from "@/types/api";
import {
  KEY_PERMISSIONS,
  canonicalScopes,
  scopesForPreset,
  type KeyPreset,
} from "@/utils/keyPermissions";

const show = defineModel<boolean>("show", { required: true });

const props = defineProps<{
  preset?: KeyPreset;
  editing?: Pick<ApiKeyOut, "id" | "name" | "scopes"> | null;
}>();

const emit = defineEmits<{
  created: [payload: ApiKeyCreated];
  saved: [];
  removed: [];
}>();

const message = useMessage();
const formRef = ref<FormInst | null>(null);
const saving = ref(false);
const removing = ref(false);

const form = ref({
  name: "",
  scopes: [] as string[],
});

const isEditing = computed(() => Boolean(props.editing));
const fullAccess = computed(() => form.value.scopes.includes("admin"));
const canSave = computed(() => form.value.name.trim().length > 0 && form.value.scopes.length > 0);

function isOn(id: string) {
  return fullAccess.value || form.value.scopes.includes(id);
}

function locked(id: string) {
  return fullAccess.value && id !== "admin";
}

function setScope(id: string, on: boolean) {
  if (id === "admin") {
    form.value.scopes = on
      ? ["admin"]
      : ["read", "recognize", "enroll", "update", "delete"];
    return;
  }
  if (fullAccess.value) return;
  const next = new Set(form.value.scopes);
  if (on) next.add(id);
  else next.delete(id);
  form.value.scopes = canonicalScopes([...next]);
}

function reset() {
  if (props.editing) {
    form.value = {
      name: props.editing.name,
      scopes: canonicalScopes(props.editing.scopes),
    };
    return;
  }
  form.value = { name: "", scopes: scopesForPreset(props.preset ?? "default") };
}

function close() {
  show.value = false;
}

async function submit() {
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }
  const name = form.value.name.trim();
  const scopes = canonicalScopes(form.value.scopes);
  if (!scopes.length) {
    message.warning("Choose at least one permission.");
    return;
  }
  saving.value = true;
  try {
    if (props.editing) {
      await api<ApiKeyOut>(`/v1/auth/keys/${props.editing.id}`, {
        method: "PATCH",
        json: { name, scopes },
      });
      message.success("API key saved");
      emit("saved");
      close();
      return;
    }
    const res = await api<ApiKeyCreated>("/v1/auth/keys", {
      method: "POST",
      json: { name, scopes },
    });
    emit("created", res);
    close();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not save the key");
  } finally {
    saving.value = false;
  }
}

async function remove() {
  if (!props.editing) return;
  removing.value = true;
  try {
    await api(`/v1/auth/keys/${props.editing.id}`, { method: "DELETE" });
    message.success("API key deleted");
    emit("removed");
    close();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not delete the key");
  } finally {
    removing.value = false;
  }
}

watch(show, (open) => {
  if (open) reset();
});
</script>

<template>
  <NModal
    v-model:show="show"
    preset="card"
    :title="isEditing ? 'Edit API key' : 'New API key'"
    class="key-editor or-modal"
    :mask-closable="!saving && !removing"
  >
    <p class="modal-lead">
      <template v-if="isEditing">
        Change the name or what this key can do. The secret stays the same, so apps using it keep working.
      </template>
      <template v-else>
        Name the key after what will use it. Each permission works the same over the REST API and over MCP.
      </template>
    </p>

    <NForm ref="formRef" :model="form" label-placement="top" class="key-form">
      <NFormItem
        label="Name"
        path="name"
        :rule="{ required: true, message: 'Name is required', trigger: ['blur', 'input'] }"
      >
        <NInput
          v-model:value="form.name"
          maxlength="80"
          placeholder="Kitchen camera"
          :disabled="saving"
        />
      </NFormItem>
    </NForm>

    <section class="perm-block">
      <h3 class="perm-heading">Permissions</h3>
      <p class="perm-intro">
        These apply to the REST API and to assistant tools. Turn on only what this key should do.
      </p>
      <div
        v-for="item in KEY_PERMISSIONS"
        :key="item.id"
        class="perm-row"
        :class="{ 'is-locked': locked(item.id) }"
        @click="locked(item.id) ? undefined : setScope(item.id, !isOn(item.id))"
      >
        <span class="perm-row__copy">
          <span class="perm-row__label">{{ item.label }}</span>
          <span class="perm-row__hint">{{ item.hint }}</span>
        </span>
        <NCheckbox
          :checked="isOn(item.id)"
          :disabled="locked(item.id) || saving"
          @update:checked="(on: boolean) => setScope(item.id, on)"
          @click.stop
        />
      </div>
    </section>

    <template #footer>
      <div class="or-modal-footer" :class="{ 'is-split': isEditing }">
        <NPopconfirm v-if="isEditing" @positive-click="remove">
          <template #trigger>
            <NButton type="error" quaternary :loading="removing" :disabled="saving">Delete key</NButton>
          </template>
          Delete “{{ form.name || editing?.name }}”? Apps and assistants using it will stop working.
        </NPopconfirm>
        <div class="footer-actions">
          <NButton :disabled="saving || removing" @click="close">Cancel</NButton>
          <NButton type="primary" :loading="saving" :disabled="!canSave || removing" @click="submit">
            {{ isEditing ? "Save" : "Create key" }}
          </NButton>
        </div>
      </div>
    </template>
  </NModal>
</template>

<style scoped>
.modal-lead {
  margin: 0 0 20px;
  max-width: 40rem;
  font-size: 0.9375rem;
  line-height: 1.5;
  color: var(--or-text-2, var(--n-text-color-2));
}

.key-form :deep(.n-form-item) {
  margin-bottom: 8px;
}

.perm-block {
  margin-top: 22px;
}

.perm-heading {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
}

.perm-intro {
  margin: 6px 0 0;
  font-size: 0.875rem;
  line-height: 1.45;
  color: var(--or-text-3, var(--n-text-color-3));
}

.perm-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 14px 0;
  border-top: 1px solid var(--or-line, var(--n-border-color));
  cursor: pointer;
}

.perm-row:first-of-type {
  margin-top: 8px;
}

.perm-row.is-locked {
  cursor: default;
}

.perm-row__copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.perm-row__label {
  font-size: 0.9375rem;
  font-weight: 600;
}

.perm-row__hint {
  font-size: 0.875rem;
  line-height: 1.45;
  color: var(--or-text-3, var(--n-text-color-3));
}

.or-modal-footer.is-split {
  justify-content: space-between;
}

.footer-actions {
  display: flex;
  gap: 12px;
}
</style>
