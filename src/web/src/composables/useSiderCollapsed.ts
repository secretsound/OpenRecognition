import { ref, watch } from "vue";

const STORAGE_KEY = "or-sider-collapsed";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function writeCollapsed(value: boolean) {
  try {
    localStorage.setItem(STORAGE_KEY, String(value));
  } catch {
    /* ignore */
  }
}

const collapsed = ref(readCollapsed());
let skipNextPersist = false;

watch(collapsed, (value) => {
  if (skipNextPersist) {
    skipNextPersist = false;
    return;
  }
  writeCollapsed(value);
});

export function useSiderCollapsed() {
  function setCollapsed(value: boolean, persist = true) {
    if (!persist) skipNextPersist = true;
    collapsed.value = value;
    if (persist) writeCollapsed(value);
  }

  function restoreDesktopPreference() {
    skipNextPersist = true;
    collapsed.value = readCollapsed();
  }

  return { collapsed, setCollapsed, restoreDesktopPreference };
}
