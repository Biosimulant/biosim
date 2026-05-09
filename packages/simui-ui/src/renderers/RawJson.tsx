import React from "react";

export default function RawJson({ data }: { data: Record<string, unknown>; isFullscreen?: boolean }) {
  return (
    <pre className="raw-json-renderer">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
