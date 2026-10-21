/** Human-readable reason when getUserMedia / mic is blocked. */
export function microphoneBlockedMessage(err?: unknown): string {
  if (typeof window !== "undefined" && !window.isSecureContext) {
    return (
      "Microphone requires a secure connection (HTTPS). " +
      "Use the Vite dev server at https://localhost:5173 (npm run dev in web/), " +
      "or open the app via https://127.0.0.1 — plain http:// on a remote hostname will not work."
    );
  }
  if (err instanceof DOMException) {
    if (err.name === "NotAllowedError") {
      return "Microphone permission was denied. Allow access in your browser settings and try again.";
    }
    if (err.name === "NotFoundError") {
      return "No microphone was found on this device.";
    }
    if (err.name === "NotReadableError") {
      return "Microphone is in use by another app or could not be opened.";
    }
  }
  if (err instanceof Error && err.message) return err.message;
  return "Could not access the microphone.";
}

export function isSecureEnoughForMic(): boolean {
  return typeof window !== "undefined" && window.isSecureContext;
}
