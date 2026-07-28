#!/usr/bin/env python3
"""
Health Monitor — periodically checks the Legis Agent backend
and reports issues to syslog / stderr.

Can be used as:
  - systemd timer (see docs/deployment.md)
  - cron job
  - pre-deploy smoke check

Exit codes:
  0 = healthy
  1 = degraded (latency > threshold, non-critical)
  2 = unhealthy (down, 5xx, critical)
"""

import argparse
import logging
import os
import sys
import time
import urllib.error
import urllib.request

# ── Defaults ──────────────────────────────────────────
DEFAULT_URL = "http://localhost:8000/health"
DEFAULT_LATENCY_WARN_MS = 3000   # 3 seconds
DEFAULT_LATENCY_CRIT_MS = 10000  # 10 seconds
DEFAULT_TIMEOUT_S = 10
DEFAULT_INTERVAL_S = 60


def setup_logging(verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("health_monitor")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] health_monitor: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    return logger


def check_health(
    url: str,
    timeout: int,
    latency_warn: int,
    latency_crit: int,
    logger: logging.Logger,
) -> int:
    """Check the health endpoint. Returns exit code 0, 1, or 2."""
    start = time.monotonic()

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = (time.monotonic() - start) * 1000
            status = resp.status

            if status == 200:
                if latency_ms > latency_crit:
                    logger.error(
                        "CRITICAL: Health check passed but latency=%.0fms "
                        "(threshold=%.0fms) on %s",
                        latency_ms,
                        latency_crit,
                        url,
                    )
                    return 2
                elif latency_ms > latency_warn:
                    logger.warning(
                        "DEGRADED: Health check passed but latency=%.0fms "
                        "(threshold=%.0fms) on %s",
                        latency_ms,
                        latency_warn,
                        url,
                    )
                    return 1
                else:
                    logger.info(
                        "OK: Health check passed (status=%d, latency=%.0fms) on %s",
                        status,
                        latency_ms,
                        url,
                    )
                    return 0
            else:
                logger.error(
                    "UNHEALTHY: Health check returned status=%d on %s",
                    status,
                    url,
                )
                return 2

    except urllib.error.HTTPError as e:
        latency_ms = (time.monotonic() - start) * 1000
        logger.error(
            "UNHEALTHY: Health check returned HTTP %d (latency=%.0fms) on %s",
            e.code,
            latency_ms,
            url,
        )
        return 2
    except urllib.error.URLError as e:
        latency_ms = (time.monotonic() - start) * 1000
        logger.error(
            "DOWN: Cannot reach %s after %.0fms — %s",
            url,
            latency_ms,
            e.reason,
        )
        return 2
    except TimeoutError:
        logger.error(
            "DOWN: Health check timed out after %ds on %s",
            timeout,
            url,
        )
        return 2


def check_alternative_ports(logger: logging.Logger) -> None:
    """Check if backend is running on alternative ports (useful after restart)."""
    common_ports = [8000, 8001, 8080]
    for port in common_ports:
        url = f"http://localhost:{port}/health"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    logger.warning(
                        "Backend found on port %d but expected on a different port. "
                        "Check LEGIS_API_URL configuration.",
                        port,
                    )
        except Exception:
            continue


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Legis Agent Health Monitor",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("LEGIS_HEALTH_URL", DEFAULT_URL),
        help=f"Health endpoint URL (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--latency-warn",
        type=int,
        default=int(os.environ.get("LEGIS_LATENCY_WARN_MS", str(DEFAULT_LATENCY_WARN_MS))),
        help=f"Latency warning threshold in ms (default: {DEFAULT_LATENCY_WARN_MS})",
    )
    parser.add_argument(
        "--latency-crit",
        type=int,
        default=int(os.environ.get("LEGIS_LATENCY_CRIT_MS", str(DEFAULT_LATENCY_CRIT_MS))),
        help=f"Latency critical threshold in ms (default: {DEFAULT_LATENCY_CRIT_MS})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("LEGIS_HEALTH_TIMEOUT", str(DEFAULT_TIMEOUT_S))),
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT_S})",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("LEGIS_HEALTH_INTERVAL", str(DEFAULT_INTERVAL_S))),
        help=f"Check interval in seconds (default: {DEFAULT_INTERVAL_S})",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously, checking at the specified interval",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()
    logger = setup_logging(args.verbose)

    if args.daemon:
        logger.info(
            "Starting health monitor daemon (interval=%ds, url=%s)",
            args.interval,
            args.url,
        )
        while True:
            code = check_health(
                args.url, args.timeout,
                args.latency_warn, args.latency_crit,
                logger,
            )
            if code >= 1:
                logger.warning("Health check degraded (exit=%d), checking alternatives...", code)
                check_alternative_ports(logger)
            time.sleep(args.interval)
    else:
        return check_health(
            args.url, args.timeout,
            args.latency_warn, args.latency_crit,
            logger,
        )


if __name__ == "__main__":
    sys.exit(main())
