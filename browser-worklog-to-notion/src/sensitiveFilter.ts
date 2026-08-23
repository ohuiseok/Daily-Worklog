export interface SensitiveFilterResult {
  action: "keep" | "mask" | "discard";
  text: string;
  reasons: string[];
}

const EMAIL_PATTERN = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
const PHONE_PATTERN = /\b(?:\+?\d{1,3}[-.\s]?)?(?:\d{2,4}[-.\s]?){2,4}\d{2,4}\b/g;
const CARD_LIKE_PATTERN = /\b(?:\d[ -]*?){13,19}\b/g;
const API_KEY_PATTERN = /\b(?:sk|pk|ntn|ghp|gho|ghu|github_pat|xoxb|xoxp)_[A-Za-z0-9_\-]{12,}\b/g;
const PRIVATE_KEY_PATTERN = /-----BEGIN [A-Z ]*PRIVATE KEY-----/;
const STRONG_SECRET_CONTEXT = /\b(password|passwd|secret|api[_-]?key|private[_-]?key|access[_-]?token|refresh[_-]?token)\b/i;

export function filterSensitiveText(text: string): SensitiveFilterResult {
  const reasons: string[] = [];

  if (PRIVATE_KEY_PATTERN.test(text)) {
    return { action: "discard", text: "", reasons: ["private_key"] };
  }

  if (API_KEY_PATTERN.test(text)) {
    return { action: "discard", text: "", reasons: ["api_key"] };
  }

  if (STRONG_SECRET_CONTEXT.test(text)) {
    return { action: "discard", text: "", reasons: ["secret_context"] };
  }

  let masked = text;
  masked = masked.replace(EMAIL_PATTERN, () => {
    reasons.push("email");
    return "[email]";
  });
  masked = masked.replace(CARD_LIKE_PATTERN, () => {
    reasons.push("card_like_number");
    return "[number]";
  });
  masked = masked.replace(PHONE_PATTERN, (match) => {
    if (digitsOnly(match).length < 9) {
      return match;
    }
    reasons.push("phone");
    return "[phone]";
  });

  return {
    action: reasons.length ? "mask" : "keep",
    text: masked,
    reasons: [...new Set(reasons)]
  };
}

function digitsOnly(value: string): string {
  return value.replace(/\D/g, "");
}
