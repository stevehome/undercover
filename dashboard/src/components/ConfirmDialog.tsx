import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

/** The dashboard's own confirmation, on a `<dialog>`, before an action that changes something. */
export function ConfirmDialog({
  title,
  confirmLabel,
  onConfirm,
  onCancel,
  children,
}: Readonly<{
  title: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  children: ReactNode;
}>) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  return (
    <dialog
      ref={dialog}
      className="confirm"
      aria-labelledby="confirm-title"
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
    >
      <h2 id="confirm-title">{title}</h2>
      {children}
      <div className="actions">
        <button type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" onClick={onConfirm}>
          {confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
