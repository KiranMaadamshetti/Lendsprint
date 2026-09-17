// Restrained semicircular PD gauge (SVG arc + HTML number overlay). pd is 0..1
const COLORS = {
  approve: "#059669",
  review: "#d97706",
  reject: "#dc2626",
  pending: "#64748b",
};

export function PdGauge({ pd = 0, decision = "pending", size = 200 }) {
  const clamped = Math.max(0, Math.min(1, pd));
  const radius = 80;
  const circumference = Math.PI * radius; // semicircle length
  const dash = circumference * clamped;
  const color = COLORS[decision] || COLORS.pending;

  return (
    <div className="flex flex-col items-center" style={{ width: size }}>
      <div className="relative" style={{ width: size, height: size * 0.62 }}>
        <svg viewBox="0 0 200 116" width={size} height={size * 0.62} data-testid="pd-gauge">
          <path d="M 16 100 A 84 84 0 0 1 184 100" fill="none" stroke="#e6e6ef" strokeWidth="12" strokeLinecap="round" />
          <path
            d="M 16 100 A 84 84 0 0 1 184 100"
            fill="none"
            stroke={color}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circumference * 1.05}`}
            style={{ transition: "stroke-dasharray 0.8s cubic-bezier(0.4,0,0.2,1)" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-1.5">
          <div className="metric-num text-[30px] font-bold leading-none" style={{ color: "#1a2440" }} data-testid="pd-gauge-value">
            {(clamped * 100).toFixed(1)}%
          </div>
          <div className="label-eyebrow mt-1">Probability of Default</div>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-3 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: "#059669" }} />Low</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: "#d97706" }} />Moderate</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: "#dc2626" }} />High</span>
      </div>
    </div>
  );
}
