'use client';

import * as React from 'react';
import { formatCurrency } from '@/lib/utils';

interface PriceConvergenceChartProps {
  buyerOffers: number[];
  sellerOffers: number[];
}

export function PriceConvergenceChart({ buyerOffers, sellerOffers }: PriceConvergenceChartProps) {
  const allPrices = [...buyerOffers, ...sellerOffers];
  if (allPrices.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-sm text-muted-foreground">
        No offer data yet
      </div>
    );
  }

  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  const priceRange = maxPrice - minPrice || 1;
  const maxRounds = Math.max(buyerOffers.length, sellerOffers.length);

  const svgW = 600;
  const svgH = 200;
  const padX = 60;
  const padY = 20;
  const chartW = svgW - padX * 2;
  const chartH = svgH - padY * 2;

  const toX = (round: number) => padX + (round / Math.max(maxRounds - 1, 1)) * chartW;
  const toY = (price: number) => padY + chartH - ((price - minPrice) / priceRange) * chartH;

  const buyerPoints = buyerOffers.map((p, i) => `${toX(i)},${toY(p)}`).join(' ');
  const sellerPoints = sellerOffers.map((p, i) => `${toX(i)},${toY(p)}`).join(' ');

  // Y-axis labels
  const yTicks = 5;
  const yLabels = Array.from({ length: yTicks }, (_, i) => {
    const price = minPrice + (priceRange / (yTicks - 1)) * i;
    return { price, y: toY(price) };
  });

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${svgW} ${svgH}`} className="w-full h-auto min-w-[400px]" preserveAspectRatio="xMidYMid meet">
        {/* Grid lines */}
        {yLabels.map(({ price, y }) => (
          <g key={price}>
            <line x1={padX} y1={y} x2={svgW - padX} y2={y} stroke="var(--border)" strokeWidth="1" strokeDasharray="4 4" />
            <text x={padX - 8} y={y + 4} textAnchor="end" className="text-[10px]" fill="var(--muted-foreground)">
              {(price / 1000).toFixed(0)}K
            </text>
          </g>
        ))}

        {/* X-axis labels */}
        {Array.from({ length: maxRounds }, (_, i) => (
          <text key={i} x={toX(i)} y={svgH - 2} textAnchor="middle" className="text-[10px]" fill="var(--muted-foreground)">
            R{i + 1}
          </text>
        ))}

        {/* Buyer line */}
        {buyerOffers.length > 1 && (
          <polyline
            points={buyerPoints}
            fill="none"
            stroke="var(--chart-1)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
        {buyerOffers.map((p, i) => (
          <circle key={`b${i}`} cx={toX(i)} cy={toY(p)} r="4" fill="var(--chart-1)" />
        ))}

        {/* Seller line */}
        {sellerOffers.length > 1 && (
          <polyline
            points={sellerPoints}
            fill="none"
            stroke="var(--chart-2)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
        {sellerOffers.map((p, i) => (
          <circle key={`s${i}`} cx={toX(i)} cy={toY(p)} r="4" fill="var(--chart-2)" />
        ))}

        {/* Latest points highlighted */}
        {buyerOffers.length > 0 && (
          <circle cx={toX(buyerOffers.length - 1)} cy={toY(buyerOffers[buyerOffers.length - 1])} r="6" fill="var(--chart-1)" opacity="0.5" />
        )}
        {sellerOffers.length > 0 && (
          <circle cx={toX(sellerOffers.length - 1)} cy={toY(sellerOffers[sellerOffers.length - 1])} r="6" fill="var(--chart-2)" opacity="0.5" />
        )}
      </svg>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-2">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-chart-1 rounded" />
          <span className="text-xs text-muted-foreground">Buyer</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-chart-2 rounded" />
          <span className="text-xs text-muted-foreground">Seller</span>
        </div>
      </div>
    </div>
  );
}
