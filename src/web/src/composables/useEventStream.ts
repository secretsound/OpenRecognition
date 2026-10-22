import { onBeforeUnmount, onMounted, ref } from "vue";
import type { ConsoleEvent } from "@/types/api";

/** Same-origin EventSource; session cookie is sent automatically. */
export function useEventStream(onEvent: (event: ConsoleEvent) => void) {
  const connected = ref(false);
  let source: EventSource | null = null;

  function close() {
    source?.close();
    source = null;
    connected.value = false;
  }

  function connect() {
    close();
    const es = new EventSource("/v1/events/stream");
    source = es;
    es.onopen = () => {
      connected.value = true;
    };
    es.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data) as ConsoleEvent);
      } catch {
        /* ignore malformed frames */
      }
    };
    es.onerror = () => {
      connected.value = false;
    };
  }

  onMounted(connect);
  onBeforeUnmount(close);

  return { connected };
}
