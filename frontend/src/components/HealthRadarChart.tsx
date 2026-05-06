"use client";

interface RadarAxis {
  label: string;
  tooltip: string;
  value: number;
}

interface HealthRadarChartProps {
  axes: RadarAxis[];
}

export default function HealthRadarChart({ axes }: HealthRadarChartProps) {
  const size = 200;
  const cx = size / 2;
  const cy = size / 2;
  const maxR = 72;
  const levels = 4;
  const n = axes.length;

  const getPoint = (i: number, r: number) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  };

  const gridPolygons = Array.from({ length: levels }, (_, level) => {
    const r = ((level + 1) / levels) * maxR;
    return axes.map((_, i) => `${getPoint(i, r).x},${getPoint(i, r).y}`).join(" ");
  });

  const dataPoints = axes.map((axis, i) => getPoint(i, (axis.value / 100) * maxR));
  const dataPolygon = dataPoints.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <div className="w-full flex justify-center">
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[200px] h-auto">
        {/* Grid polygons */}
        {gridPolygons.map((points, i) => (
          <polygon key={i} points={points} fill="none" stroke="#232833" strokeWidth={0.8} />
        ))}
        {/* Axis lines */}
        {axes.map((_, i) => {
          const outer = getPoint(i, maxR);
          return <line key={i} x1={cx} y1={cy} x2={outer.x} y2={outer.y} stroke="#232833" strokeWidth={0.8} />;
        })}
        {/* Data polygon */}
        <polygon points={dataPolygon} fill="#2d7aff" fillOpacity={0.18} stroke="#2d7aff" strokeWidth={1.5} />
        {/* Dots */}
        {dataPoints.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={3.5} fill="#2d7aff" stroke="#0d0f12" strokeWidth={1.2} />
        ))}
        {/* Labels */}
        {axes.map((axis, i) => {
          const lp = getPoint(i, maxR + 20);
          const score = Math.round(axis.value);
          const scoreColor = score >= 60 ? "#25c26e" : score >= 30 ? "#8b8fa3" : "#ff554a";
          return (
            <g key={i}>
              <title>{axis.tooltip}</title>
              <text
                x={lp.x}
                y={lp.y - 5}
                textAnchor="middle"
                dominantBaseline="middle"
                fill="#8b8fa3"
                fontSize={8.5}
                fontFamily="monospace"
              >
                {axis.label}
              </text>
              <text
                x={lp.x}
                y={lp.y + 6}
                textAnchor="middle"
                dominantBaseline="middle"
                fill={scoreColor}
                fontSize={8}
                fontFamily="monospace"
                fontWeight="bold"
              >
                {score}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
