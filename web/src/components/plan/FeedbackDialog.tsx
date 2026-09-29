import { useState } from "react";
import type { PlanSession } from "@douini/shared";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

const RATINGS = ["tres_facile", "facile", "controlee", "difficile", "intenable"];
const FATIGUE = ["none", "light", "moderate", "heavy"];
const PAIN = ["none", "light", "moderate", "severe"];

export function FeedbackDialog({ session, onClose, onSubmit }: {
  session: PlanSession;
  onClose: () => void;
  onSubmit: (feedback: { pace_rating: string; rpe: number; fatigue_level: string; pain_level: string }) => void;
}) {
  const [paceRating, setPaceRating] = useState("controlee");
  const [rpe, setRpe] = useState(5);
  const [fatigue, setFatigue] = useState("none");
  const [pain, setPain] = useState("none");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <Card className="w-full max-w-md" >
        <div onClick={(e) => e.stopPropagation()}>
          <h3 className="mb-4 text-lg font-semibold">Feedback — {session.workout || session.type}</h3>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Allure ressentie</label>
              <select value={paceRating} onChange={(e) => setPaceRating(e.target.value)} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                {RATINGS.map((r) => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">RPE (1-10): {rpe}</label>
              <input type="range" min={1} max={10} value={rpe} onChange={(e) => setRpe(+e.target.value)} className="w-full" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Fatigue</label>
              <select value={fatigue} onChange={(e) => setFatigue(e.target.value)} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                {FATIGUE.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Douleur</label>
              <select value={pain} onChange={(e) => setPain(e.target.value)} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                {PAIN.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>Annuler</Button>
            <Button onClick={() => onSubmit({ pace_rating: paceRating, rpe, fatigue_level: fatigue, pain_level: pain })}>Valider</Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
