import { createContext, useContext } from "react";
import type { Handler } from "./types";

export const MeContext = createContext<Handler | null>(null);

/** The signed-in handler; null outside the signed-in pages. */
export function useMe(): Handler | null {
  return useContext(MeContext);
}
