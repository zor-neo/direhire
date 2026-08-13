const PATTERNS: Array<[string, string, RegExp]> = [
  ["greenhouse", "Greenhouse", /(?:boards|job-boards)\.greenhouse\.io\//i],
  ["lever", "Lever", /jobs\.(?:eu\.)?lever\.co\//i],
  ["ashby", "Ashby", /jobs\.ashby(?:hq)?\.(?:com|io)\//i],
  ["recruitee", "Recruitee", /\.recruitee\.com\//i],
  ["personio", "Personio", /\.jobs\.personio\.de\//i],
  ["pinpoint", "Pinpoint", /\.pinpointhq\.com\//i],
];

export function detectAdapter(url: string): { key: string; label: string } | null {
  for (const [key, label, pattern] of PATTERNS) {
    if (pattern.test(url)) return { key, label };
  }
  return null;
}
