import { useEffect, useState } from "react";
import { onSignedIn } from "./auth";

/** Whether a handler is signed in; null until the browser has said. */
export function useSignedIn(): boolean | null {
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  useEffect(() => onSignedIn(setSignedIn), []);
  return signedIn;
}
