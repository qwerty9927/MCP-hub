import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Mock window.matchMedia for next-themes
Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    })),
});

// Mock ResizeObserver
class MockResizeObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
}
global.ResizeObserver = MockResizeObserver as any;

if (typeof window !== "undefined") {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    window.HTMLElement.prototype.hasPointerCapture = vi.fn();
    window.HTMLElement.prototype.releasePointerCapture = vi.fn();
}

// Mock crypto.randomUUID
if (!global.crypto) {
    (global as any).crypto = {};
}
if (!global.crypto.randomUUID) {
    global.crypto.randomUUID = () => "12345678-1234-1234-1234-123456789abc" as `${string}-${string}-${string}-${string}-${string}`;
}
