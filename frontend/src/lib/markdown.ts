export function stripFrontmatter(md: string): string { return md.replace(/^---[\s\S]*?---\n/, ""); }
export function hasTable(md: string): boolean { return /\|.*\|/.test(md); }
