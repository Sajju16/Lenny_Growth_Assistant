import React from 'react';

export function BrandLogo({ className = "w-8 h-8" }) {
  return (
    <div className={`rounded-lg bg-[#1C1B1B] p-1.5 flex items-center justify-center shrink-0 shadow-sm ${className}`}>
      <svg viewBox="0 0 24 24" fill="none" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
        {/* Modern Lenny Growth monogram */}
        <path
          d="M6 5v14h12"
          stroke="#FFFFFF"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="15.5" cy="8.5" r="3" fill="#1D4ED8" />
      </svg>
    </div>
  );
}
