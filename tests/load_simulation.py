# -*- coding: utf-8 -*-
"""Simulation de charge du backend — N étudiants simultanés (chiffres du tableau 3:X7).

Reproduit le trafic réel du SDK, requête par requête et signature par signature :

  1. ouverture de session   POST /api/v1/machine/sessions/           canonique project|exam|student|issued_at
  2. lot d'événements       POST /api/v1/machine/events/              canonique project|session|issued_at
     (toutes les 7 s, comme `EventPipeline.ts` — événements informatifs) ;
     un événement critique part immédiatement, hors lot (comme `sendNow`)
  3. signal de vie          POST /api/v1/machine/logs/                canonique project|sdk-logs|issued_at
     (toutes les 45 s, comme `Diagnostics.ts`, plus un heartbeat au démarrage)
  4. fermeture de session   POST /api/v1/machine/sessions/<id>/close/ canonique project|session|issued_at

Chaque étudiant simulé est un fil léger avec une connexion HTTP persistante (keep-alive),
comme un navigateur réel. Le script mesure le débit atteint (requêtes/s) et la latence
des requêtes (médiane, p95, max), puis affiche un résumé du palier.

Usage (les clés sont celles du projet de démonstration, détenues par le serveur du développeur) :
  python tests/load_simulation.py --students 10 --duration 45 \
      --project-id <uuid> --public-key pk_live_... --secret-key sk_live_...

Deux familles de paliers :

  * rythme du SDK (défaut)   : chaque étudiant suit le cadencement réel (lot/7 s, signal de
    vie/45 s, critique immédiat) pendant `--duration` secondes ; mesure le débit en req/s ;
  * volume (`--volume-events`) : chaque étudiant déverse N événements dans SA session par lots
    de `--volume-batch`, le plus vite possible ; mesure le débit d'ingestion en événements/s
    et la latence par requête (10, 20, 100, 1 000 événements par session).

Le script ne s'exécute PAS sous pytest (pas de préfixe test_) : une épreuve de charge n'a
rien à faire dans la suite d'intégration continue, elle se lance à la main.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import http.client
import json
import threading
import time
import uuid
from datetime import datetime, timezone

# --- Constantes du trafic simulé -------------------------------------------------------------

BASE_URL = "http://127.0.0.1:8000"
EXAM_ID = "loadtest"
SDK_VERSION = "1.0.0"

# Types d'événements du SDK : informatifs (mis en lot) et critiques (envoi immédiat).
INFORMATIVE_TYPES = ["FOCUS_LOST", "TAB_SWITCH", "HANDS_VISIBLE_SUSTAINED"]
CRITICAL_TYPE = "MULTIPLE_FACES"

# Rythmes du SDK (identiques au code source, cf. 02_SDK.md §13.4).
BATCH_INTERVAL_S = 7.0       # EventPipeline.ts : flushIntervalMs ?? 7000
HEARTBEAT_INTERVAL_S = 45.0  # SdkConfig.ts : heartbeatIntervalMs ?? 45000
CRITICAL_EVERY_S = 20.0      # un événement critique simulé toutes les 20 s


def canonical_sign(secret_key: str, message: str) -> str:
    """Signature HMAC-SHA256 hexadécimale — même construction que le SDK et le backend."""
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()


def iso_now() -> str:
    """Horodatage ISO-8601 UTC, format attendu par l'ingestion (USE_TZ=True)."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Config:
    """Paramètres d'une campagne : cible, projet signé, examen simulé."""

    def __init__(self, args: argparse.Namespace) -> None:
        after_scheme = args.base_url.partition("://")[2]
        self.host, _, port = after_scheme.partition(":")
        self.port = int(port or 80)
        self.project_id = args.project_id
        self.public_key = args.public_key
        self.secret_key = args.secret_key
        self.exam_id = args.exam_id


class Metrics:
    """Compteurs partagés entre les fils, agrégés en fin de palier."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.ok = 0
        self.events_ok = 0
        self.errors: list[str] = []
        self.latencies: list[float] = []

    def record(self, status: int, latency_ms: float, err: Exception | None) -> None:
        with self.lock:
            if err is not None:
                self.errors.append(f"{type(err).__name__}: {err}")
            elif 200 <= status < 300:
                self.ok += 1
                self.latencies.append(latency_ms)
            else:
                self.errors.append(f"HTTP {status}")

    def add_events(self, count: int) -> None:
        with self.lock:
            self.events_ok += count

    def summary(self, elapsed_s: float, students: int) -> str:
        lat = sorted(self.latencies)
        n = len(lat)

        def pct(p: float) -> float:
            return lat[min(int(p * n), n - 1)] if n else float("nan")

        rps = self.ok / elapsed_s if elapsed_s > 0 else 0.0
        theoretical = students * (1 / BATCH_INTERVAL_S + 1 / HEARTBEAT_INTERVAL_S)
        lines = [
            f"  requêtes OK          : {self.ok}",
            f"  durée                : {elapsed_s:.1f} s",
            f"  débit mesuré         : {rps:.1f} req/s",
            f"  débit théorique      : {theoretical:.1f} req/s"
            " (1 lot/7 s + 1 signal de vie/45 s par étudiant)",
            f"  latence médiane      : {pct(0.50):.0f} ms" if n else "  latence médiane      : n/a",
            f"  latence p95          : {pct(0.95):.0f} ms" if n else "  latence p95          : n/a",
            f"  latence max          : {max(lat):.0f} ms" if n else "  latence max          : n/a",
            f"  erreurs              : {len(self.errors)}",
        ]
        if self.errors:
            lines.append("  exemples d'erreurs   : " + "; ".join(self.errors[:3]))
        return "\n".join(lines)

    def summary_volume(self, elapsed_s: float, students: int, per_student: int, batch: int) -> str:
        lat = sorted(self.latencies)
        n = len(lat)

        def pct(p: float) -> float:
            return lat[min(int(p * n), n - 1)] if n else float("nan")

        eps = self.events_ok / elapsed_s if elapsed_s > 0 else 0.0
        lines = [
            f"  événements ingérés   : {self.events_ok} (cible {students * per_student})",
            f"  durée                : {elapsed_s:.1f} s",
            f"  débit d'ingestion    : {eps:.0f} événements/s",
            f"  requêtes OK          : {self.ok} (lots de {batch} événement(s))",
            f"  latence médiane      : {pct(0.50):.0f} ms" if n else "  latence médiane      : n/a",
            f"  latence p95          : {pct(0.95):.0f} ms" if n else "  latence p95          : n/a",
            f"  latence max          : {max(lat):.0f} ms" if n else "  latence max          : n/a",
            f"  erreurs              : {len(self.errors)}",
        ]
        if self.errors:
            lines.append("  exemples d'erreurs   : " + "; ".join(self.errors[:3]))
        return "\n".join(lines)


class StudentSim:
    """Un étudiant simulé : sa connexion persistante, son rythme, ses requêtes signées."""

    def __init__(self, index: int, cfg: Config, metrics: Metrics) -> None:
        self.student_id = f"sim-{index:04d}"
        self.cfg = cfg
        self.metrics = metrics
        self.conn: http.client.HTTPConnection | None = None
        self.session_id: str | None = None
        self.last_status = 0
        self.stop_at = 0.0

    # --- transport ----------------------------------------------------------------------- #

    def _connect(self) -> None:
        self.conn = http.client.HTTPConnection(self.cfg.host, self.cfg.port, timeout=15)

    def _post(self, path: str, body: dict, signature: str, read_body: bool = False) -> dict:
        """Une requête POST signée. Mesure la latence, gère la connexion morte."""
        if self.conn is None:
            self._connect()
        assert self.conn is not None
        payload = json.dumps(body).encode()
        headers = {
            "Content-Type": "application/json",
            "X-ExamSDK-Public-Key": self.cfg.public_key,
            "X-ExamSDK-Signature": signature,
        }
        start = time.perf_counter()
        status, data, err = 0, {}, None
        try:
            self.conn.request("POST", path, body=payload, headers=headers)
            res = self.conn.getresponse()
            status = res.status
            if read_body:
                data = json.loads(res.read() or b"{}")
            else:
                res.read()  # vide le corps, la connexion reste réutilisable
        except Exception as exc:  # connexion cassée : réouverte au prochain appel
            err = exc
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
        self.last_status = status
        latency_ms = (time.perf_counter() - start) * 1000.0
        self.metrics.record(status, latency_ms, err)
        return data

    # --- scénario d'un étudiant ----------------------------------------------------------- #

    def run(self) -> None:
        issued = lambda: int(time.time())  # noqa: E731

        # 1. Ouverture de session (idempotente côté backend) ; on lit `session_id`.
        issued_at = issued()
        message = f"{self.cfg.project_id}|{self.cfg.exam_id}|{self.student_id}|{issued_at}"
        data = self._post(
            "/api/v1/machine/sessions/",
            {"exam_id": self.cfg.exam_id, "student_id": self.student_id, "issued_at": issued_at},
            canonical_sign(self.cfg.secret_key, message),
            read_body=True,
        )
        self.session_id = data.get("session_id")

        seq = 0
        next_batch = time.monotonic() + BATCH_INTERVAL_S
        next_beat = time.monotonic() + 1.0  # heartbeat de démarrage, puis toutes les 45 s
        next_critical = time.monotonic() + CRITICAL_EVERY_S

        while time.monotonic() < self.stop_at:
            now = time.monotonic()
            if now >= next_batch:
                next_batch += BATCH_INTERVAL_S
                seq += 1
                self.send_events(seq, critical=False)
            if now >= next_critical:
                next_critical += CRITICAL_EVERY_S
                seq += 1
                self.send_events(seq, critical=True)  # hors lot, immédiat
            if now >= next_beat:
                next_beat += HEARTBEAT_INTERVAL_S
                self.send_heartbeat()
            time.sleep(0.05)

        # 4. Fermeture propre de la session.
        if self.session_id:
            issued_at = issued()
            message = f"{self.cfg.project_id}|{self.session_id}|{issued_at}"
            self._post(
                f"/api/v1/machine/sessions/{self.session_id}/close/",
                {"invalid": False, "issued_at": issued_at, "session_id": self.session_id},
                canonical_sign(self.cfg.secret_key, message),
            )
        self._disconnect()

    def send_events(self, seq: int, critical: bool) -> None:
        if not self.session_id:
            return
        issued_at = int(time.time())
        message = f"{self.cfg.project_id}|{self.session_id}|{issued_at}"
        if critical:
            events = [{
                "event_id": str(uuid.uuid4()),
                "type": CRITICAL_TYPE,
                "occurred_at": iso_now(),
                "confidence_score": 0.9,
                "metadata": {"count": 2, "durationMs": 3500, "simulated": True},
            }]
        else:
            events = [{
                "event_id": str(uuid.uuid4()),
                "type": INFORMATIVE_TYPES[seq % len(INFORMATIVE_TYPES)],
                "occurred_at": iso_now(),
                "confidence_score": 0.9,
                "metadata": {"simulated": True},
            }]
        self._post(
            "/api/v1/machine/events/",
            {"session_id": self.session_id, "issued_at": issued_at, "events": events},
            canonical_sign(self.cfg.secret_key, message),
        )

    def send_heartbeat(self) -> None:
        issued_at = int(time.time())
        message = f"{self.cfg.project_id}|sdk-logs|{issued_at}"
        self._post(
            "/api/v1/machine/logs/",
            {
                "issued_at": issued_at,
                "session_id": self.session_id,
                "logs": [{
                    "kind": "heartbeat",
                    "level": "info",
                    "sdk_version": SDK_VERSION,
                    "occurred_at": iso_now(),
                }],
            },
            canonical_sign(self.cfg.secret_key, message),
        )

    def _disconnect(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None


def run_scenario(students: int, duration: float, cfg: Config) -> None:
    print(f"\n=== Palier : {students} étudiants simultanés, {duration:.0f} s ===", flush=True)
    metrics = Metrics()
    stop = time.monotonic() + duration
    sims = [StudentSim(i, cfg, metrics) for i in range(students)]
    for sim in sims:
        sim.stop_at = stop

    t0 = time.monotonic()
    threads = [threading.Thread(target=sim.run, daemon=True) for sim in sims]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=duration + 60)
    elapsed = time.monotonic() - t0
    print(metrics.summary(elapsed, students), flush=True)


def run_volume_scenario(
    students: int, events_per_student: int, batch_size: int, cfg: Config
) -> None:
    """Un étudiant déverse `events_per_student` événements dans SA session, par lots de
    `batch_size`. Mesure le débit d'INGESTION (événements/s) et la latence par requête,
    indépendamment du rythme temporel du SDK (qui borne lui la cadence à 1 lot / 7 s).
    """
    print(
        f"\n=== Volume : {students} étudiants × {events_per_student} événements/session, "
        f"lots de {batch_size} ===",
        flush=True,
    )
    metrics = Metrics()

    def work(index: int) -> None:
        sim = StudentSim(index, cfg, metrics)
        issued_at = int(time.time())
        message = f"{cfg.project_id}|{cfg.exam_id}|{sim.student_id}|{issued_at}"
        data = sim._post(
            "/api/v1/machine/sessions/",
            {"exam_id": cfg.exam_id, "student_id": sim.student_id, "issued_at": issued_at},
            canonical_sign(cfg.secret_key, message),
            read_body=True,
        )
        sim.session_id = data.get("session_id")
        remaining = events_per_student
        while remaining > 0 and sim.session_id:
            count = min(batch_size, remaining)
            remaining -= count
            events = [
                {
                    "event_id": str(uuid.uuid4()),
                    "type": INFORMATIVE_TYPES[i % len(INFORMATIVE_TYPES)],
                    "occurred_at": iso_now(),
                    "confidence_score": 0.9,
                    "metadata": {"simulated": True},
                }
                for i in range(count)
            ]
            issued_at = int(time.time())
            message = f"{cfg.project_id}|{sim.session_id}|{issued_at}"
            sim._post(
                "/api/v1/machine/events/",
                {"session_id": sim.session_id, "issued_at": issued_at, "events": events},
                canonical_sign(cfg.secret_key, message),
            )
            if 200 <= sim.last_status < 300:
                metrics.add_events(count)
        if sim.session_id:
            issued_at = int(time.time())
            message = f"{cfg.project_id}|{sim.session_id}|{issued_at}"
            sim._post(
                f"/api/v1/machine/sessions/{sim.session_id}/close/",
                {"invalid": False, "issued_at": issued_at, "session_id": sim.session_id},
                canonical_sign(cfg.secret_key, message),
            )
        sim._disconnect()

    threads = [threading.Thread(target=work, args=(i,), daemon=True) for i in range(students)]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=600)
    elapsed = time.monotonic() - t0
    print(metrics.summary_volume(elapsed, students, events_per_student, batch_size), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulation de charge du backend ExamSDK.")
    parser.add_argument("--students", type=int, default=10, help="étudiants simultanés")
    parser.add_argument("--duration", type=float, default=45.0, help="durée du palier en s")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--secret-key", required=True)
    parser.add_argument("--exam-id", default=EXAM_ID)
    parser.add_argument(
        "--volume-events",
        type=int,
        default=0,
        help="mode volume : N événements par session (0 = mode rythme du SDK)",
    )
    parser.add_argument(
        "--volume-batch",
        type=int,
        default=1,
        help="mode volume : taille des lots d'événements par requête",
    )
    args = parser.parse_args()
    cfg = Config(args)
    if args.volume_events > 0:
        run_volume_scenario(args.students, args.volume_events, args.volume_batch, cfg)
    else:
        run_scenario(args.students, args.duration, cfg)


if __name__ == "__main__":
    main()
