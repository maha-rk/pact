import "@testing-library/jest-dom/vitest";

// jsdom (the test DOM environment) doesn't implement IntersectionObserver.
// The landing page uses it to trigger both the scroll-reveal animation
// and the proof-strip count-up -- tests need elements to actually become
// "visible" (synchronously, since nothing in jsdom really scrolls) so
// that visibility-gated behavior is exercised, not just present-but-inert.
class MockIntersectionObserver {
  #callback: IntersectionObserverCallback;

  constructor(callback: IntersectionObserverCallback) {
    this.#callback = callback;
  }

  observe(target: Element) {
    this.#callback([{ isIntersecting: true, target } as IntersectionObserverEntry], this as never);
  }

  unobserve() {}
  disconnect() {}
}

// @ts-expect-error -- test-environment polyfill, not a spec-accurate implementation
globalThis.IntersectionObserver = MockIntersectionObserver;
