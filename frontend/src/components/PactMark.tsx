// Pact's mark: two forms meeting and overlapping -- two independent
// parties (buyer, vendor) converging on one shared point of agreement.
// Not a letter in a box; a real, small, deliberate piece of identity
// reused everywhere the wordmark appears (sidebar, landing topbar).
export function PactMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="var(--accent)" />
      <circle cx="13" cy="16" r="7.5" fill="#fff" />
      <circle cx="20" cy="16" r="7.5" fill="none" stroke="#fff" strokeWidth="1.8" />
    </svg>
  );
}
