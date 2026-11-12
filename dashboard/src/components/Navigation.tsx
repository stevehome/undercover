import { NavLink } from "react-router";

const PAGES = [
  ["/", "Queue"],
  ["/scoreboard", "Scoreboard"],
  ["/improvement", "Improvement"],
  ["/configuration", "Configuration"],
  ["/settings", "Settings"],
] as const;

/** The pages, with the one you are on marked. */
export function Navigation() {
  return (
    <nav className="top-nav" aria-label="Pages">
      {PAGES.map(([to, label]) => (
        <NavLink key={to} to={to} end={to === "/"}>
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
