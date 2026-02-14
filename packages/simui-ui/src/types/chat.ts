export type ChatMessageRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatMessageRole;
  content: string;
  createdAt: string;
  runId?: string | null;
};

export type ChatThread = {
  id: string;
  spaceId: string;
  title?: string | null;
  messages: ChatMessage[];
};

export type ChatAdapter = {
  getThread: () => Promise<ChatThread>;
  sendMessage: (payload: { content: string; onChunk?: (chunk: string) => void }) => Promise<ChatMessage>;
};
