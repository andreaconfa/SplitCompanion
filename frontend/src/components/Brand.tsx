/** Split Companion monogram. */
export function BrandSymbol({ className = '' }: { className?: string }) {
  return <svg className={`brand-symbol ${className}`} viewBox="0 0 1024 1024" aria-hidden="true" focusable="false">
    <rect width="1024" height="1024" rx="240" fill="#4936CC" />
    <path fill="#F0FFFC" d="M535 524L613 535C712 552 767 608 767 691C767 784 692 848 580 848H330V742H575C614 742 639 723 639 693C639 669 620 651 582 645L515 634Z" />
    <path fill="#A8C8FF" d="M694 218H444c-132 0-226 89-226 207 0 105 72 172 181 190l90 15 20-111-80-15c-58-10-84-36-84-77 0-54 43-89 105-89h244z" />
  </svg>;
}
export function Brand({ className = '', compact = false }: { className?: string; compact?: boolean }) {
  return <div className={`brand ${className}`} aria-label={compact ? 'Split Companion' : undefined}><BrandSymbol />{!compact && <span>Split<span className="brand-sub">Companion</span></span>}</div>;
}
