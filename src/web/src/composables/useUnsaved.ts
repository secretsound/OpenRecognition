import { onUnmounted, type Ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";

export function useUnsavedGuard(dirty: Ref<boolean>, message = "Discard unsaved changes?") {
  function confirmLeave(): boolean {
    if (!dirty.value) return true;
    return window.confirm(message);
  }

  onBeforeRouteLeave(() => confirmLeave());

  const onBeforeUnload = (e: BeforeUnloadEvent) => {
    if (!dirty.value) return;
    e.preventDefault();
    e.returnValue = "";
  };
  window.addEventListener("beforeunload", onBeforeUnload);
  onUnmounted(() => window.removeEventListener("beforeunload", onBeforeUnload));

  return { confirmLeave };
}
