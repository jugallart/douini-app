#!/usr/bin/env python3
"""Migrate SQLite (douini-run) → PostgreSQL (douini-app).

Usage:
  python migrate_sqlite_to_pg.py --sqlite-path /path/to/douini.db --postgres-url "postgresql://douini:douini@localhost:5432/douini"
  python migrate_sqlite_to_pg.py --sqlite-path ... --postgres-url ... --dry-run
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from urllib.parse import urlparse

import psycopg


def migrate(sqlite_path: str, pg_url: str, dry_run: bool = False) -> None:
    lite = sqlite3.connect(sqlite_path)
    lite.row_factory = sqlite3.Row

    if dry_run:
        print("DRY RUN — no writes")
    else:
        pg = psycopg.connect(pg_url)
        pg.autocommit = False
        cur = pg.cursor()

    id_map: dict[str, dict[int, int]] = {}

    tables = [
        "users",
        "profile",
        "plans",
        "plan_sessions",
        "session_feedback",
        "plan_adjustments",
        "race_results",
        "profile_vdot_history",
    ]

    for table in tables:
        rows = lite.execute(f"SELECT * FROM {table}").fetchall()
        print(f"{table}: {len(rows)} rows")
        if dry_run or not rows:
            continue

        if table == "users":
            for row in rows:
                cur.execute(
                    "INSERT INTO users (id, email, password_hash, email_verified, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING RETURNING id",
                    (row["id"], row["username"], row["password_hash"], True, row["created_at"], row["created_at"]),
                )
                new_id = cur.fetchone()[0]
                id_map.setdefault("users", {})[row["id"]] = new_id
            pg.commit()

        elif table == "profile":
            for row in rows:
                uid = id_map["users"].get(row["user_id"], row["user_id"])
                cur.execute(
                    "INSERT INTO profile (user_id, vdot, weekly_volume_km, training_days, "
                    "target_weekly_km, sessions_per_week, race_distance, weeks, target_time, "
                    "experience, current_weekly_km, current_longest_run, long_run_day, preferred_days) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (user_id) DO NOTHING",
                    (uid, row["vdot"], row.get("weekly_volume_km", 0),
                     row.get("training_days_json", "[]"),
                     row.get("target_weekly_km"), row.get("sessions_per_week", 4),
                     row.get("race_distance"), row.get("weeks", 12), row.get("target_time"),
                     row.get("experience", "intermediaire"),
                     row.get("current_weekly_km"), row.get("current_longest_run"),
                     row.get("long_run_day"), row.get("preferred_days_json", "[]")),
                )
            pg.commit()

        elif table == "plans":
            for row in rows:
                uid = id_map["users"].get(row["user_id"], row["user_id"])
                cur.execute(
                    "INSERT INTO plans (id, user_id, name, distance, weeks, vdot, start_date, "
                    "goal_time, sessions_json, settings_json, status, race_date, mode, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (id) DO NOTHING RETURNING id",
                    (row["id"], uid, row["name"], row["distance"], row["weeks"], row["vdot"],
                     row.get("start_date"), row.get("goal_time"),
                     row.get("sessions_json", "[]"), row.get("settings_json", "{}"),
                     row.get("status", "active"), row.get("race_date"),
                     row.get("mode", "prod"), row["created_at"]),
                )
                new_id = cur.fetchone()[0]
                id_map.setdefault("plans", {})[row["id"]] = new_id
            pg.commit()

        elif table == "plan_sessions":
            for row in rows:
                pid = id_map["plans"].get(row["plan_id"], row["plan_id"])
                cur.execute(
                    "INSERT INTO plan_sessions (plan_id, week, day, scheduled_date, type, "
                    "workout_name, distance_km, status, garmin_workout_id, garmin_activity_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (plan_id, week, day) DO NOTHING",
                    (pid, row["week"], row["day"], row.get("scheduled_date"),
                     row["type"], row.get("workout_name"), row.get("distance_km", 0),
                     row.get("status", "pending"),
                     row.get("garmin_workout_id"), row.get("garmin_activity_id")),
                )
            pg.commit()

        elif table == "session_feedback":
            for row in rows:
                cur.execute(
                    "INSERT INTO session_feedback (plan_session_id, user_id, pace_rating, rpe, "
                    "fatigue_level, fatigue_duration, pain_level, pain_impact, pain_location, "
                    "pain_onset, pain_evolution, temp_cause, difficulty_streak, rules_version, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (plan_session_id) DO NOTHING",
                    (row["plan_session_id"], row.get("user_id"),
                     row.get("pace_rating"), row.get("rpe"),
                     row.get("fatigue_level"), row.get("fatigue_duration"),
                     row.get("pain_level"), row.get("pain_impact"),
                     row.get("pain_location"), row.get("pain_onset"),
                     row.get("pain_evolution"), row.get("temp_cause"),
                     row.get("difficulty_streak", 0), row.get("rules_version", "2026.1"),
                     row.get("created_at")),
                )
            pg.commit()

        elif table == "plan_adjustments":
            for row in rows:
                pid = id_map["plans"].get(row["plan_id"], row["plan_id"])
                cur.execute(
                    "INSERT INTO plan_adjustments (plan_id, trigger_session_id, status, reason, "
                    "confidence, horizon_weeks, old_vdot, new_vdot, diff_json, rules_version, created_at, reviewed_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (pid, row.get("trigger_session_id"), row.get("status", "proposed"),
                     row.get("reason"), row.get("confidence"), row.get("horizon_weeks"),
                     row.get("old_vdot"), row.get("new_vdot"),
                     row.get("diff_json", "[]"), row.get("rules_version", "2026.1"),
                     row["created_at"], row.get("reviewed_at")),
                )
            pg.commit()

        elif table == "race_results":
            for row in rows:
                uid = id_map["users"].get(row["user_id"], row["user_id"])
                cur.execute(
                    "INSERT INTO race_results (user_id, plan_id, distance, actual_time, race_date, "
                    "derived_vdot, notes, location, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (uid, id_map.get("plans", {}).get(row.get("plan_id", 0)),
                     row["distance"], row.get("actual_time"), row.get("race_date"),
                     row.get("derived_vdot"), row.get("notes"), row.get("location"),
                     row["created_at"]),
                )
            pg.commit()

        elif table == "profile_vdot_history":
            for row in rows:
                uid = id_map["users"].get(row["user_id"], row["user_id"])
                cur.execute(
                    "INSERT INTO profile_vdot_history (user_id, vdot, recorded_at, source, plan_id, is_provisional) "
                    "VALUES (%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (uid, row["vdot"], row["recorded_at"],
                     row.get("source", "manual"),
                     id_map.get("plans", {}).get(row.get("plan_id", 0)),
                     row.get("is_provisional", False)),
                )
            pg.commit()

    if not dry_run:
        cur.close()
        pg.close()
    lite.close()
    print("Migration complete.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Migrate SQLite → PostgreSQL")
    ap.add_argument("--sqlite-path", required=True)
    ap.add_argument("--postgres-url", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pg_url = args.postgres_url.replace("postgresql+psycopg://", "postgresql://")
    migrate(args.sqlite_path, pg_url, args.dry_run)


if __name__ == "__main__":
    main()
