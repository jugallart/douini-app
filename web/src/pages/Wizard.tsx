import { useState } from "react";
import { useNavigate } from "react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { profileApi, plansApi } from "@douini/shared";
import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Card } from "../components/ui/Card";
import { Alert } from "../components/ui/Alert";

const DISTANCES = ["5k", "10k", "semi", "marathon"];
const EXPERIENCES = ["debutant", "intermediaire", "avance"];
const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const DAY_LABELS: Record<string, string> = { mon: "Lun", tue: "Mar", wed: "Mer", thu: "Jeu", fri: "Ven", sat: "Sam", sun: "Dim" };

export function Wizard() {
  const [step, setStep] = useState(0);
  const [experience, setExperience] = useState("intermediaire");
  const [distance, setDistance] = useState("10k");
  const [targetTime, setTargetTime] = useState("");
  const [sessionsPerWeek, setSessionsPerWeek] = useState(4);
  const [trainingDays, setTrainingDays] = useState<string[]>(["tue", "thu", "sat", "sun"]);
  const [longRunDay, setLongRunDay] = useState("sun");
  const [currentWeeklyKm, setCurrentWeeklyKm] = useState(30);
  const [currentLongestRun, setCurrentLongestRun] = useState(10);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const qc = useQueryClient();

  const generateMutation = useMutation({
    mutationFn: async () => {
      await profileApi.update({
        experience,
        race_distance: distance,
        target_time: targetTime || null,
        sessions_per_week: sessionsPerWeek,
        training_days: trainingDays,
        long_run_day: longRunDay,
        current_weekly_km: currentWeeklyKm,
        current_longest_run: currentLongestRun,
      });
      await plansApi.generate({
        distance,
        target_time: targetTime || undefined,
        sessions_per_week: sessionsPerWeek,
        training_days: trainingDays,
        long_run_day: longRunDay,
        current_weekly_km: currentWeeklyKm,
        current_longest_run: currentLongestRun,
        experience,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plans"] });
      navigate("/");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Erreur"),
  });

  function toggleDay(day: string) {
    setTrainingDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort((a, b) => DAYS.indexOf(a) - DAYS.indexOf(b)),
    );
  }

  const steps = [
    {
      title: "Votre niveau",
      content: (
        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">Expérience</label>
            <div className="flex gap-2">
              {EXPERIENCES.map((exp) => (
                <button
                  key={exp}
                  onClick={() => setExperience(exp)}
                  className={`rounded-lg border px-4 py-2 text-sm capitalize ${
                    experience === exp ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-300"
                  }`}
                >
                  {exp}
                </button>
              ))}
            </div>
          </div>
          <Input
            label="Volume hebdomadaire actuel (km)"
            type="number"
            value={currentWeeklyKm}
            onChange={(e) => setCurrentWeeklyKm(+e.target.value)}
          />
          <Input
            label="Plus longue sortie actuelle (km)"
            type="number"
            value={currentLongestRun}
            onChange={(e) => setCurrentLongestRun(+e.target.value)}
          />
        </div>
      ),
    },
    {
      title: "Objectif",
      content: (
        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">Distance cible</label>
            <div className="flex gap-2">
              {DISTANCES.map((d) => (
                <button
                  key={d}
                  onClick={() => setDistance(d)}
                  className={`rounded-lg border px-4 py-2 text-sm ${
                    distance === d ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-300"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
          <Input
            label="Temps visé (optionnel, ex: 45:00)"
            value={targetTime}
            onChange={(e) => setTargetTime(e.target.value)}
            placeholder="MM:SS"
          />
        </div>
      ),
    },
    {
      title: "Planning",
      content: (
        <div className="space-y-4">
          <Input
            label="Séances par semaine"
            type="number"
            min={2}
            max={7}
            value={sessionsPerWeek}
            onChange={(e) => setSessionsPerWeek(+e.target.value)}
          />
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">Jours d'entraînement</label>
            <div className="flex flex-wrap gap-2">
              {DAYS.map((day) => (
                <button
                  key={day}
                  onClick={() => toggleDay(day)}
                  className={`rounded-lg border px-3 py-1.5 text-sm ${
                    trainingDays.includes(day) ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-300"
                  }`}
                >
                  {DAY_LABELS[day]}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">Jour sortie longue</label>
            <select
              value={longRunDay}
              onChange={(e) => setLongRunDay(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            >
              {DAYS.map((day) => (
                <option key={day} value={day}>{DAY_LABELS[day]}</option>
              ))}
            </select>
          </div>
        </div>
      ),
    },
    {
      title: "Récapitulatif",
      content: (
        <div className="space-y-3 text-sm text-gray-700">
          <p><strong>Niveau:</strong> <span className="capitalize">{experience}</span></p>
          <p><strong>Objectif:</strong> {distance} {targetTime && `en ${targetTime}`}</p>
          <p><strong>Séances:</strong> {sessionsPerWeek}/semaine les {trainingDays.map((d) => DAY_LABELS[d]).join(", ")}</p>
          <p><strong>Volume actuel:</strong> {currentWeeklyKm} km/sem, sortie longue {currentLongestRun} km</p>
        </div>
      ),
    },
  ];

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl">
        <div className="mb-6 flex items-center justify-between">
          {steps.map((s, i) => (
            <div key={i} className="flex items-center">
              <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                i <= step ? "bg-brand-600 text-white" : "bg-gray-200 text-gray-500"
              }`}>
                {i + 1}
              </div>
              {i < steps.length - 1 && <div className={`h-0.5 w-12 ${i < step ? "bg-brand-600" : "bg-gray-200"}`} />}
            </div>
          ))}
        </div>
        <Card>
          <h2 className="mb-4 text-lg font-semibold">{steps[step].title}</h2>
          {steps[step].content}
          {error && <div className="mt-4"><Alert>{error}</Alert></div>}
          <div className="mt-6 flex justify-between">
            <Button variant="secondary" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>
              Retour
            </Button>
            {step < steps.length - 1 ? (
              <Button onClick={() => setStep((s) => s + 1)}>Continuer</Button>
            ) : (
              <Button loading={generateMutation.isPending} onClick={() => generateMutation.mutate()}>
                Générer mon plan
              </Button>
            )}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
