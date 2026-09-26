/**
 * Copy text with the Clipboard API; `false` when it is missing or refuses (for example without
 * a user gesture or on an insecure origin). Start the call inside the click handler, before any
 * `await`, so the browser still treats it as part of the user's gesture.
 *
 * When `selected` is given (a text field whose content is already selected), the legacy
 * `execCommand("copy")` is tried as a last resort.
 */
export async function copyText(
  text: string,
  selected?: HTMLTextAreaElement,
): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall through to the legacy path, or report failure.
  }
  if (!selected || typeof document.execCommand !== "function") {
    return false;
  }
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  }
}
