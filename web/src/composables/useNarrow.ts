import { onMounted, onUnmounted, ref } from "vue";

export function useNarrow(maxWidth = 768) {
  const narrow = ref(false);
  let media: MediaQueryList | null = null;

  function update() {
    narrow.value = media?.matches ?? window.matchMedia(`(max-width: ${maxWidth}px)`).matches;
  }

  onMounted(() => {
    media = window.matchMedia(`(max-width: ${maxWidth}px)`);
    update();
    media.addEventListener("change", update);
  });

  onUnmounted(() => {
    media?.removeEventListener("change", update);
  });

  return narrow;
}
