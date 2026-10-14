import { listOcrImages } from "../api/client";
import { formatOcrImageErrorMessage } from "./validationMessages";

export { buildParseFailureNotification, type ParseFailureNotification } from "./parseFailureNotification";

export async function collectOcrParseFailureMessages(imageIds: string[]): Promise<string[]> {
  if (!imageIds.length) {
    return [];
  }

  const candidateSet = new Set(imageIds);
  const response = await listOcrImages({ parse_status: "failed", limit: 500 });
  const messages: string[] = [];
  const seen = new Set<string>();

  for (const image of response.items) {
    if (!candidateSet.has(image.id) || !image.error_message?.trim()) {
      continue;
    }
    const formatted = formatOcrImageErrorMessage(image.error_message);
    if (!formatted || seen.has(formatted)) {
      continue;
    }
    seen.add(formatted);
    messages.push(formatted);
  }

  return messages;
}

export async function collectOcrImageFailureMessage(imageId: string): Promise<string | null> {
  const messages = await collectOcrParseFailureMessages([imageId]);
  return messages[0] ?? null;
}
