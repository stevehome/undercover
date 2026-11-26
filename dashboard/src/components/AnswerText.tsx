import { Link } from "react-router";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

const CLAIM_ID = /(?<![[\w/])CLM-\d+\b(?!\])/g;

/** Write each claim id as a link to its page, before the markdown is read. */
const linkClaims = (text: string) =>
  text.replace(CLAIM_ID, (id) => `[${id}](/claims/${id})`);

/**
 * A Copilot answer in markdown, shown formatted. Raw HTML in it is shown as text,
 * never as markup, and a claim id links to the claim's page.
 */
export function AnswerText({ text }: Readonly<{ text: string }>) {
  return (
    <div className="answer-text">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) =>
            href?.startsWith("/claims/") ? (
              <Link to={href} className="mono">
                {children}
              </Link>
            ) : (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            ),
        }}
      >
        {linkClaims(text)}
      </Markdown>
    </div>
  );
}
