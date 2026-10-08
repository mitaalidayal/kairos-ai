let uid = 0;

/** Unique DOM ids for label/for and aria-describedby pairs. */
export function nextId(prefix = 'x'): string {
  uid += 1;
  return `kai-${prefix}-${uid}`;
}
