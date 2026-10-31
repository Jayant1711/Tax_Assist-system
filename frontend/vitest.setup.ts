// Global test setup: DOM matcher assertions (toBeInTheDocument, ...)
// registered on vitest's expect.
import '@testing-library/jest-dom/vitest';

// jsdom does not implement scrolling APIs used by the chat transcript.
if (typeof Element !== 'undefined' && !Element.prototype.scrollTo) {
  Element.prototype.scrollTo = () => {};
}
