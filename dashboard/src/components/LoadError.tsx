/** Says the latest poll failed, in a corner so the page does not move; its data stays. */
export function LoadError() {
  return (
    <p role="alert" className="load-error">
      Could not load the latest.
    </p>
  );
}
