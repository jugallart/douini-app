# Phase 1: Feedback Engine Completion

**Items**: P12 (VDOT recalibration), P13 (streak detection), P14 (non-quality suppression), P15 (recovery auto-restore)
**Priorité**: Critique
**Fichiers touchés**: `backend/douini/services/feedback.py`, `backend/douini/routes/sessions.py`

## Contexte

Le service feedback actuel gere `suspend_quality` et `lighten_workout` mais ignore 4 actions produites par `vdot.evaluate_feedback()`. Le feedback est le coeur adaptatif du produit.

## P12: VDOT recalibration dans feedback

`evaluate_feedback()` produit `kind="recalibrate_vdot"` (too_hard RPE>=9 2eme fois => -1% VDOT, too_easy RPE<=2 2eme fois => +1% VDOT).

douini-run: `services.process_session_feedback` calcule new_vdot, update profile, genere diff entry, sauve adjustment.

Actions:
- Ajouter handler `recalibrate_vdot` dans `feedback.py`
- Calculer new_vdot: `current_vdot * factor` (factor from `vdot.recalibrate_vdot()`), cap ±1
- Update `profile.vdot`
- Generer diff entry (old_vdot -> new_vdot)
- Sauver `plan_adjustment` avec `reason="recalibrate_vdot"`

## P13: Previous-same-zone streak detection

douini-run: cherche la session precedente de meme zone (quality) dans le plan, lit son feedback, extrait `difficulty_streak`.

douini-app actuel: prend `previous_streak` comme parametre caller (frontend doit le fournir).

Actions:
- Avant `evaluate_feedback()`, query `session_feedback` pour la derniere session quality completee avant celle-ci dans le meme plan
- Extraire `difficulty_streak` du feedback precedent
- Passer `previous_streak` calcule a `evaluate_feedback()`
- Supprimer le parametre du request schema (ou le rendre optionnel, fallback calcul DB)

## P14: Non-quality session suppression

douini-run: si la session n'est pas une session quality, les propositions basees sur pace/difficulty sont supprimees (pas de recalibrate_vdot, pas de progression_trial sur une easy run).

Actions:
- Avant traitement feedback, check `session.type` / `session.workout_name` contre `session_types.json` pour determiner si quality
- Si non-quality: ignorer les kinds `recalibrate_vdot`, `local_progression_trial`, `monitor_difficulty`
- Garder pain/fatigue rules (suspend_running, suspend_quality) — elles s'appliquent a toutes sessions

## P15: Recovery auto-restore on clean feedback

douini-run: quand feedback n'a ni pain ni fatigue (clean), restore les ajustements precedents (si un suspend_quality etait actif, le lever).

Actions:
- Si feedback est "clean" (pain=none, fatigue=none/light):
  - Query `plan_adjustments` actifs (status=applied, non-expires) pour ce plan
  - Pour chaque adjustment `suspend_quality` ou `lighten_next_quality`: restaurer les sessions modifiees depuis `diff_json`
  - Marquer adjustment `status=restored`
- Logique de restore reutilise P9 (Phase 2)

## Tests

- `test_feedback_recalibrate_vdot`: feedback too_hard x2 => profile.vdot baisse
- `test_feedback_streak_from_db`: streak calcule depuis DB, pas caller
- `test_feedback_non_quality_suppressed`: easy run + too_hard => pas de recalibrate
- `test_feedback_clean_restores`: clean feedback => adjustment precedent restored

## AC

- [x] `recalibrate_vdot` handler implemente et testé
- [x] Streak calcule depuis DB (plus de param caller)
- [x] Non-quality sessions ne declenchent pas recalibrate/progression
- [x] Clean feedback restore les ajustements suspend/lighten actifs
- [x] Tests passent (410 domain + self-checks)
