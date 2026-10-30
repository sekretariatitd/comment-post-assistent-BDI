import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useAuth } from "../auth/AuthContext";

/** Live updates: refresh posts/drafts and activity whenever the server reports a change
 * (draft.created, draft.updated, post.created), whether a person or the worker caused it. */
export function useQueueEvents() {
  const qc = useQueryClient();
  const { token } = useAuth();

  useEffect(() => {
    if (!token || typeof WebSocket === "undefined") return;
    let socket: WebSocket | null = null;
    let retryMs = 1000;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const connect = () => {
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const url = `${proto}://${window.location.host}/api/v1/ws/queue?token=${encodeURIComponent(token)}`;
      socket = new WebSocket(url);
      socket.onopen = () => {
        retryMs = 1000;
      };
      socket.onmessage = () => {
        qc.invalidateQueries({ queryKey: ["posts"] });
        qc.invalidateQueries({ queryKey: ["activity"] });
      };
      socket.onclose = () => {
        if (stopped) return;
        timer = setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 2, 30_000);
      };
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, [token, qc]);
}
