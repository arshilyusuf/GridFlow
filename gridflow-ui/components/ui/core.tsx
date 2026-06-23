// File: components/ui/core.tsx
import React from 'react';

export const Card = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-zinc-950 border border-zinc-800 rounded-xl shadow-sm text-zinc-100 ${className}`}>
    {children}
  </div>
);

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger";
  icon?: React.ElementType;
}

export const Button = ({ children, variant = "primary", className = "", icon: Icon, ...props }: ButtonProps) => {
  const baseStyle = "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50 h-9 px-4 py-2";
  const variants = {
    primary: "bg-zinc-100 text-zinc-900 hover:bg-zinc-200",
    secondary: "bg-zinc-900 text-zinc-100 border border-zinc-800 hover:bg-zinc-800",
    danger: "bg-red-900 text-red-100 hover:bg-red-800"
  };
  return (
    <button className={`${baseStyle} ${variants[variant]} ${className}`} {...props}>
      {Icon && <Icon className="w-4 h-4 mr-2" />}
      {children}
    </button>
  );
};

export const Badge = ({ children, variant = "default" }: { children: React.ReactNode; variant?: "default" | "success" | "error" | "warning" }) => {
  const variants = {
    default: "bg-zinc-800 text-zinc-100",
    success: "bg-emerald-950 text-emerald-400 border border-emerald-800",
    error: "bg-red-950 text-red-400 border border-red-800",
    warning: "bg-amber-950 text-amber-400 border border-amber-800"
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors ${variants[variant]}`}>
      {children}
    </span>
  );
};