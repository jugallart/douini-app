import { ButtonHTMLAttributes, forwardRef } from "react";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger";
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ variant = "primary", loading, className = "", children, disabled, ...rest }, ref) => {
    const base = "rounded-lg px-4 py-2 text-sm font-medium transition disabled:opacity-50";
    const variants = {
      primary: "bg-brand-600 text-white hover:bg-brand-700",
      secondary: "bg-gray-200 text-gray-800 hover:bg-gray-300",
      danger: "bg-red-600 text-white hover:bg-red-700",
    };
    return (
      <button ref={ref} className={`${base} ${variants[variant]} ${className}`} disabled={disabled || loading} {...rest}>
        {loading ? "…" : children}
      </button>
    );
  },
);
Button.displayName = "Button";
