import json
import logging
import re
import secrets
import unicodedata

from ...db import get_connection, return_connection
from .credentials import hash_password
from .onboarding import ensure_auth_tables

logger = logging.getLogger("modern_backend.auth.provisioning")


def _username_part(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", normalized.lower())


def _driver_username(first_name: str | None, last_name: str | None, employee_id: int) -> str:
    return f"{_username_part(last_name)}{_username_part(first_name)[:1]}" or f"driver{employee_id}"


def provision_2026_chauffeur_accounts() -> int:
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
            eligible_employee_ids = [row[0] for row in chauffeurs]
            secured = 0
            if eligible_employee_ids:
                cur.execute(
                    """
                    SELECT u.user_id
                    FROM users u
                    JOIN driver_auth_state s ON s.user_id = u.user_id
                    JOIN driver_user_links l ON l.user_id = s.user_id
                    WHERE s.must_change_password = TRUE
                      AND s.bootstrap_password_randomized_at IS NULL
                      AND l.employee_id = ANY(%s)
                      AND LOWER(COALESCE(u.role, '')) IN ('driver', 'operator')
                    """,
                    (eligible_employee_ids,),
                )
                for (user_id,) in cur.fetchall():
                    cur.execute(
                        """
                        UPDATE users
                        SET password_hash = %s,
                            failed_login_attempts = 0,
                            locked_until = NULL,
                            session_version = COALESCE(session_version, 1) + 1,
                            updated_at = NOW()
                        WHERE user_id = %s
                        """,
                        (hash_password(secrets.token_urlsafe(32)), user_id),
                    )
                    cur.execute(
                        """
                        UPDATE driver_auth_state
                        SET bootstrap_password_randomized_at = NOW(),
                            updated_at = NOW()
                        WHERE user_id = %s
                        """,
                        (user_id,),
                    )
                    secured += 1
                cur.execute(
                    """
                    DELETE FROM driver_auth_challenges c
                    USING driver_auth_state s, driver_user_links l
                    WHERE c.user_id = s.user_id
                      AND l.user_id = s.user_id
                      AND s.must_change_password = TRUE
                      AND l.employee_id = ANY(%s)
                    """,
                    (eligible_employee_ids,),
                )
                cur.execute(
                    """
                    UPDATE web_sessions ws
                    SET revoked_at = NOW()
                    FROM driver_user_links l
                    JOIN driver_auth_state s ON s.user_id = l.user_id
                    WHERE ws.employee_id = l.employee_id
                      AND s.must_change_password = TRUE
                      AND l.employee_id = ANY(%s)
                      AND ws.revoked_at IS NULL
                    """,
                    (eligible_employee_ids,),
                )
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
                        hash_password(secrets.token_urlsafe(32)),
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
                    INSERT INTO driver_auth_state (
                        user_id, must_change_password, bootstrap_password_randomized_at
                    )
                    VALUES (%s, TRUE, NOW())
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (user_id,),
                )
                created += 1
                usernames.add(username)
                linked_employee_ids.add(employee_id)
        conn.commit()
        logger.info(
            "Provisioned %s and secured %s pending chauffeur account(s)",
            created,
            secured,
        )
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
