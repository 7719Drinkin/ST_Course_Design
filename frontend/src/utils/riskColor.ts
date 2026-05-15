export function riskColor(level: string) {
  if (level === 'High') return 'volcano'
  if (level === 'Medium') return 'gold'
  return 'green'
}
