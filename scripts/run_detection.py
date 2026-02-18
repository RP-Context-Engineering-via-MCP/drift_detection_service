"""Manual drift detection execution script."""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.drift_detector import DriftDetector
from app.models.drift import DriftSeverity


def setup_logging(verbose: bool = False, debug: bool = False):
    """Configure logging based on verbosity flags."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def print_event(event, verbose: bool = False):
    """Pretty-print a drift event."""
    print(f"  📊 {event.drift_type.value}")
    print(f"     Score: {event.drift_score:.3f}")
    print(f"     Severity: {event.severity.value}")
    print(f"     Confidence: {event.confidence:.3f}")
    print(f"     Targets: {', '.join(event.affected_targets)}")

    if verbose:
        print(f"     Event ID: {event.drift_event_id}")
        print(f"     Detected: {datetime.fromtimestamp(event.detected_at)}")
        print(f"     Evidence:")
        for key, value in event.evidence.items():
            print(f"       - {key}: {value}")
    print()


def main():
    """Run drift detection for a user."""
    parser = argparse.ArgumentParser(
        description="Run drift detection for a user",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_detection.py user_123
  python scripts/run_detection.py user_123 --verbose
  python scripts/run_detection.py user_123 --debug --dry-run
        """,
    )

    parser.add_argument(
        "user_id",
        help="User ID to detect drift for",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output (show more details)",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run detection but don't persist events (not implemented yet)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose, debug=args.debug)

    # Run detection
    print(f"\n🔍 Running drift detection for user: {args.user_id}\n")

    try:
        detector = DriftDetector()
        events = detector.detect_drift(args.user_id)

        if not events:
            print(f"✅ No drift detected for {args.user_id}")
            print("   Either no significant changes or insufficient data.\n")
            return 0

        # Print results
        print(f"⚠️  Detected {len(events)} drift event(s):\n")

        for event in events:
            print_event(event, verbose=args.verbose)

        # Summary by severity
        severity_counts = {}
        for event in events:
            severity = event.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        print("Summary by severity:")
        for severity in [
            DriftSeverity.STRONG_DRIFT.value,
            DriftSeverity.MODERATE_DRIFT.value,
            DriftSeverity.WEAK_DRIFT.value,
        ]:
            count = severity_counts.get(severity, 0)
            if count > 0:
                print(f"  {severity}: {count}")

        print()
        return 0

    except Exception as e:
        print(f"\n❌ Error during drift detection: {e}\n", file=sys.stderr)
        if args.debug:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
