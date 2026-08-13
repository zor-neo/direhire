export interface SearchPlatform {
  key: string;
  name: string;
  regions: string[];
  tier: string;
  search_capable: boolean;
  availability: string;
  logo_filename: string;
  description: string;
}

interface PlatformCardProps {
  platform: SearchPlatform;
  selected: boolean;
  disabled: boolean;
  onToggle: (key: string) => void;
}

export function PlatformCard({ platform, selected, disabled, onToggle }: PlatformCardProps) {
  const initials = platform.name
    .split(/\s+/)
    .map((word) => word[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <label className={`platform-card${selected ? " selected" : ""}${disabled ? " disabled" : ""}`}>
      <input
        type="checkbox"
        checked={selected}
        disabled={disabled}
        onChange={() => onToggle(platform.key)}
      />
      <span className="platform-identity" aria-hidden="true">{initials}</span>
      <span className="platform-copy">
        <strong>{platform.name}</strong>
        <small>{platform.description}</small>
      </span>
    </label>
  );
}
