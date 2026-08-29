import json
import logging
import re
import unicodedata

from ...db import get_connection, return_connection
from ...settings import get_settings
from .credentials import hash_password
from .onboarding import ensure_auth_tables

logger = logging.getLogger("modern_backend.auth.provisioning")


def _username_part(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", normalized.lower())


def _driver_username(first_name: str | None, last_name: str | None, employee_id: int) -> str:
    return f"{_username_part(last_name)}{_username_part(first_name)[:1]}" or f"driver{employee_id}"


def provision_2026_chauffeur_accounts() -> int:
    settings = get_settings()
    initial_password = settings.driver_initial_password
    conn = get_connection()
    lock_acquired = False
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(20260829)")
            lock_acquired = bool(cur.fetchone()[0])
            if not lock_acquired:
                logger.info("Driver account provisioning is already running")
                return 0
            cur.execute(
                """
                SELECT DISTINCT
                    e.employee_id, e.first_name, e.last_name, e.email
                FROM employees e
                JOIN charters c
                  ON c.assigned_driver_id = e.employee_id
                  OR c.employee_id = e.employee_id
                  OR LOWER(TRIM(COALESCE(c.driver, ''))) = LOWER(
                      TRIM(COALESCE(e.first_name, '') || ' ' || COALESCE(e.last_name, ''))
                  )
                WHERE c.charter_date >= DATE '2026-01-01'
                  AND c.charter_date < DATE '2027-01-01'
                  AND LOWER(COALESCE(e.employee_category, 'driver'))
                      IN ('driver', 'chauffeur', 'operator')
                  AND LOWER(COALESCE(e.employment_status, e.status, 'active')) = 'active'
                ORDER BY e.employee_id
                """
            )
            chauffeurs = cur.fetchall()
            cur.execute("SELECT user_id, LOWER(username) FROM users")
            existing = cur.fetchall()
            usernames = {row[1] for row in existing}
            cur.execute("SELECT employee_id FROM driver_user_links")
            linked_employee_ids = {row[0] for row in cur.fetchall()}
            cur.execute(
                """
                SELECT u.user_id, u.username, u.email
                FROM users u
                WHERE LOWER(COALESCE(u.role, '')) IN ('driver', 'operator')
                """
            )
            legacy_driver_ids = set()
            for user_id, username, user_email in cur.fetchall():
                matches = []
                for employee_id, first_name, last_name, employee_email in chauffeurs:
                    previous_username = ".".join(
                        part
                        for part in (
                            _username_part(first_name),
                            _username_part(last_name),
                        )
                        if part
                    )
                    expected_username = _driver_username(first_name, last_name, employee_id)
                    email_matches = bool(
                        user_email
                        and employee_email
                        and user_email.strip().lower() == employee_email.strip().lower()
                    )
                    if (
                        username.lower()
                        in {
                            expected_username,
                            previous_username,
                        }
                        or email_matches
                    ):
                        matches.append(employee_id)
                if len(matches) != 1 or matches[0] in linked_employee_ids:
                    continue
                employee_id = matches[0]
                cur.execute(
                    """
                    INSERT INTO driver_user_links (user_id, employee_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (user_id, employee_id),
                )
                if cur.rowcount:
                    legacy_driver_ids.add(employee_id)
            linked_employee_ids.update(legacy_driver_ids)
            sms_ready = bool(
                settings.twilio_account_sid
                and settings.twilio_auth_token
                and settings.twilio_from_number
            )
            if not initial_password or not sms_ready:
                conn.commit()
                logger.warning(
                    "New driver account provisioning skipped: private password "
                    "and SMS settings must be configured"
                )
                return 0
            password_hash = hash_password(initial_password)
            created = 0

            for employee_id, first_name, last_name, email in chauffeurs:
                if employee_id in linked_employee_ids:
                    continue
                base = _driver_username(first_name, last_name, employee_id)
                username = base
                suffix = 0
                while username in usernames:
                    suffix += 1
                    username = (
                        f"{base}.{employee_id}" if suffix == 1 else f"{base}.{employee_id}.{suffix}"
                    )

                cur.execute(
                    """
                    INSERT INTO users (
                        username, email, password_hash, role, status,
                        permissions
                    )
                    VALUES (%s, %s, %s, 'driver', 'active', %s::jsonb)
                    ON CONFLICT DO NOTHING
                    RETURNING user_id
                    """,
                    (
                        username,
                        email or f"{username}@driver.invalid",
                        password_hash,
                        json.dumps({"modules": ["chauffeur_self_service"]}),
                    ),
                )
                user_row = cur.fetchone()
                if not user_row:
                    logger.warning(
                        "Skipped chauffeur account for employee_id=%s due to an account conflict",
                        employee_id,
                    )
                    continue
                user_id = user_row[0]
                cur.execute(
                    """
                    INSERT INTO driver_user_links (user_id, employee_id)
                    VALUES (%s, %s)
                    """,
                    (user_id, employee_id),
                )
                cur.execute(
                    """
                    INSERT INTO driver_auth_state (user_id, must_change_password)
                    VALUES (%s, TRUE)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (user_id,),
                )
                created += 1
                usernames.add(username)
                linked_employee_ids.add(employee_id)
        conn.commit()
        logger.info("Provisioned %s chauffeur account(s) for 2026 runs", created)
        return created
    except Exception:
        conn.rollback()
        raise
    finally:
        if lock_acquired:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(20260829)")
                conn.commit()
            except Exception:
                conn.rollback()
        return_connection(conn)
