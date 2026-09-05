/**
 * Chat transport.
 *
 * The reply arrives as Server-Sent Events. EventSource cannot POST or send an
 * Authorization header, so this reads the stream off fetch() directly.
 */
import { getAccessToken, refreshAccessToken } from "@/lib/api";

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
const PREFIX = `${BASE}/api/v1`;

/** Emit a buffered reply through the same onEvent contract the UI already handles. */
function replayAsEvents(body, onEvent) {
  for (const tool of body.tool_calls ?? []) {
    onEvent({ type: "tool", name: tool.name, label: tool.label, input: tool.input ?? {} });
  }
  if (body.content) onEvent({ type: "text", delta: body.content });
  onEvent({
    type: "done",
    message_id: body.message_id,
    tools_used: body.tool_calls ?? [],
    provider: body.provider,
    model: body.model,
  });
}

export async function streamMessage({ conversationId, content, onEvent, signal }) {
  // VITE_CHAT_STREAMING=false forces the buffered path on hosts where SSE is
  // known not to survive the proxy.
  const streamingEnabled = import.meta.env.VITE_CHAT_STREAMING !== "false";
  const url =
    `${PREFIX}/ai/chat/conversations/${conversationId}/messages` +
    (streamingEnabled ? "" : "?stream=false");

  const post = (token) =>
    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ content }),
      signal,
    });

  let response = await post(getAccessToken());
  if (response.status === 401) {
    // An idle tab can hold an expired token; refresh once and retry.
    const renewed = await refreshAccessToken();
    if (renewed) response = await post(renewed);
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }

  // Some CDNs and serverless platforms buffer streaming responses: the body
  // arrives complete, or `response.body` is unavailable entirely. Rather than
  // appearing to hang, fall back to the single-response endpoint.
  const isStream = (response.headers.get("content-type") ?? "").includes("text/event-stream");
  if (!response.body || !isStream) {
    return replayAsEvents(await response.json(), onEvent);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line; a partial frame stays buffered.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(6)));
      } catch {
        /* ignore a malformed frame rather than killing the stream */
      }
    }
  }
}
