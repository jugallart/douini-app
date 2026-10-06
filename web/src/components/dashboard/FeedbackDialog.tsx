import { useState } from "react";
import type { SessionFeedbackPayload } from "@douini/shared";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

// Mirrors legacy pages/_shared.py _RATING_LABELS / _FATIGUE_OPTS / _PAIN_OPTS.
const RATINGS = { tres_facile: "Très facile", facile: "Facile", controlee: "Contrôlée", difficile: "Difficile", intenable: "Intenable" };
const FATIGUE = { none: "Aucune", light: "Légère", moderate: "Modérée", heavy: "Forte" };
const PAIN = { none: "Aucune", light: "Légère", moderate: "Modérée", severe: "Sévère" };

const select = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm";

export function FeedbackDialog({ title, description, loading, onClose, onSubmit }: {
  title: string;
  description: string;
  loading?: boolean;
  onClose: () => void;
  onSubmit: (fb: SessionFeedbackPayload) => void;
}) {
  const [rating, setRating] = useState<string | null>(null);
  const [rpe, setRpe] = useState(5);
  const [fatigue, setFatigue] = useState("none");
  const [pain, setPain] = useState("none");

  // Legacy fallback when no rating is picked.
  const paceRating = rating ?? (rpe <= 3 ? "tres_facile" : rpe >= 9 ? "intenable" : "controlee");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <Card className="w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <p className="text-xs uppercase text-gray-500">{title}</p>
        <h3 className="text-lg font-semibold">Comment s'est-elle passée ?</h3>
        <p className="mb-4 text-sm text-gray-500">{description}</p>
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Ressenti de la séance">
            {Object.entries(RATINGS).map(([v, l]) => (
              <Button key={v} type="button" variant={rating === v ? "primary" : "secondary"} aria-pressed={rating === v} onClick={() => setRating(v)}>{l}</Button>
            ))}
          </div>
          <label className="block text-sm font-medium text-gray-700">
            Effort perçu (1-10) · {rpe}
            <input type="range" min={1} max={10} value={rpe} onChange={(e) => setRpe(+e.target.value)} className="w-full" />
            <small className="text-gray-500">5 = modéré · 10 = maximum</small>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm font-medium text-gray-700">
              Niveau de fatigue
              <select value={fatigue} onChange={(e) => setFatigue(e.target.value)} className={select}>
                {Object.entries(FATIGUE).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label className="block text-sm font-medium text-gray-700">
              Douleurs
              <select value={pain} onChange={(e) => setPain(e.target.value)} className={select}>
                {Object.entries(PAIN).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button loading={loading} onClick={() => onSubmit({ pace_rating: paceRating, rpe, fatigue_level: fatigue, pain_level: pain })}>Valider</Button>
        </div>
      </Card>
    </div>
  );
}
