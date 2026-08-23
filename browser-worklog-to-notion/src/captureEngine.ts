export interface CaptureConfig {
  minChars: number;
  maxSnapshotChars: number;
  maxChunkChars: number;
}

export interface TextChunkDraft {
  text: string;
  charCount: number;
}

export class CaptureSession {
  private lastSnapshot = "";
  private composing = false;

  startComposition(): void {
    this.composing = true;
  }

  endComposition(): void {
    this.composing = false;
  }

  setBaseline(snapshot: string, config: CaptureConfig = DEFAULT_CAPTURE_CONFIG): void {
    this.lastSnapshot = snapshot.slice(-config.maxSnapshotChars);
  }

  update(snapshot: string, config: CaptureConfig = DEFAULT_CAPTURE_CONFIG): TextChunkDraft | null {
    if (this.composing) {
      return null;
    }

    const chunk = createChunkFromSnapshots(this.lastSnapshot, snapshot, config);
    this.lastSnapshot = snapshot;
    return chunk;
  }
}

export const DEFAULT_CAPTURE_CONFIG: CaptureConfig = {
  minChars: 8,
  maxSnapshotChars: 10_000,
  maxChunkChars: 2_000
};

export function createChunkFromSnapshots(
  previousSnapshot: string,
  currentSnapshot: string,
  config: CaptureConfig = DEFAULT_CAPTURE_CONFIG
): TextChunkDraft | null {
  const previous = normalizeSnapshot(previousSnapshot, config.maxSnapshotChars);
  const current = normalizeSnapshot(currentSnapshot, config.maxSnapshotChars);

  if (current.length <= previous.length) {
    return null;
  }

  const addedText = current.slice(sharedPrefixLength(previous, current)).trim();
  if (addedText.length < config.minChars) {
    return null;
  }

  const text = addedText.slice(0, config.maxChunkChars);
  return {
    text,
    charCount: text.length
  };
}

export function extractEditableText(element: Element): string {
  if (element instanceof HTMLTextAreaElement) {
    return element.value;
  }
  if (element instanceof HTMLInputElement) {
    return element.value;
  }
  return element.textContent ?? "";
}

export function isSupportedEditable(element: Element | null): element is HTMLElement {
  if (!element || !(element instanceof HTMLElement)) {
    return false;
  }

  if (element instanceof HTMLTextAreaElement) {
    return true;
  }

  if (element instanceof HTMLInputElement) {
    return isSupportedTextInput(element);
  }

  return (
    element.isContentEditable ||
    element.getAttribute("contenteditable") === "true" ||
    element.getAttribute("role") === "textbox" ||
    element.getAttribute("aria-multiline") === "true"
  );
}

export function findEditableElement(element: Element | null): HTMLElement | null {
  if (!element) {
    return null;
  }

  if (isSupportedEditable(element)) {
    return element;
  }

  const closest = element.closest(
    "textarea,input,[contenteditable='true'],[contenteditable=''],[role='textbox'],[aria-multiline='true']"
  );
  return isSupportedEditable(closest) ? closest : null;
}

export function shouldIgnoreEditable(element: Element): boolean {
  if (element instanceof HTMLInputElement) {
    const type = element.type.toLowerCase();
    return ["password", "hidden", "number", "tel", "email", "url"].includes(type);
  }

  return false;
}

function isSupportedTextInput(input: HTMLInputElement): boolean {
  const type = input.type.toLowerCase();
  return ["", "text", "search"].includes(type);
}

function normalizeSnapshot(value: string, maxSnapshotChars: number): string {
  return value.slice(-maxSnapshotChars);
}

function sharedPrefixLength(left: string, right: string): number {
  const maxLength = Math.min(left.length, right.length);
  let index = 0;
  while (index < maxLength && left[index] === right[index]) {
    index += 1;
  }
  return index;
}
