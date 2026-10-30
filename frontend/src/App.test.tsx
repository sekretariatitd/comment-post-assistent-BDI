import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";

import App from "./App";
import { AuthProvider } from "./auth/AuthContext";

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

// jsdom has a real WebSocket; keep the live-updates hook from opening connections in tests.
class FakeWebSocket {
  onopen = null;
  onmessage = null;
  onclose = null;
  close() {}
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("App routing", () => {
  it("redirects to the login page when there is no token", async () => {
    renderAt("/queue");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
  });

  it("shows the protected layout when the token is valid", async () => {
    localStorage.setItem("nca.token", "test-token");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ id: "1", email: "admin@example.com", role: "admin", is_active: true }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
    );
    renderAt("/queue");
    expect(await screen.findByText("admin@example.com")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Review queue" })).toBeTruthy();
  });

  it("signs out when the token is rejected", async () => {
    localStorage.setItem("nca.token", "expired");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "x" }), { status: 401 })),
    );
    renderAt("/queue");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
    expect(localStorage.getItem("nca.token")).toBeNull();
  });
});
