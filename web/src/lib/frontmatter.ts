import type { Skill } from "./types";

/**
 * Best-effort extraction of the `name` field from a SKILL.md frontmatter block.
 * Used only to tell the validator which directory the skill should live in;
 * the backend performs the authoritative parse.
 */
export function readFrontmatterName(skill: Skill | null): string | null {
  const file = skill?.files.find((f) => f.path === "SKILL.md");
  if (!file) return null;

  const match = /^---\s*\n([\s\S]*?)\n---/.exec(file.content);
  if (!match) return null;

  for (const line of match[1].split("\n")) {
    const kv = /^name\s*:\s*(.+)$/.exec(line.trim());
    if (kv) {
      return kv[1].trim().replace(/^["']|["']$/g, "");
    }
  }
  return null;
}
