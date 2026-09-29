import { InputHTMLAttributes, forwardRef } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, Props>(
  ({ label, error, className = "", ...rest }, ref) => (
    <label className="block">
      {label && <span className="mb-1 block text-sm font-medium text-gray-700">{label}</span>}
      <input
        ref={ref}
        className={`w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500 ${
          error ? "border-red-400" : "border-gray-300"
        } ${className}`}
        {...rest}
      />
      {error && <span className="mt-1 block text-xs text-red-500">{error}</span>}
    </label>
  ),
);
Input.displayName = "Input";
