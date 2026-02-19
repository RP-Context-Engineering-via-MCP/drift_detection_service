"""Simple test for drift detection."""
import sys
sys.path.insert(0, '.')

from app.core.drift_detector import DriftDetector
from app.core.snapshot_builder import SnapshotBuilder
from app.detectors.topic_emergence import TopicEmergenceDetector
from app.detectors.topic_abandonment import TopicAbandonmentDetector
from app.detectors.intensity_shift import IntensityShiftDetector
from app.detectors.preference_reversal import PreferenceReversalDetector

# Build snapshots
builder = SnapshotBuilder()
ref, cur = builder.build_reference_and_current('user_test_001')

print('\n' + '='*60)
print('REFERENCE SNAPSHOT')
print('='*60)
print(f'Targets: {ref.get_targets()}')
print(f'include_superseded: {ref.include_superseded}')
for b in ref.behaviors:
    print(f'  {b.target}: cred={b.credibility:.2f}, state={b.state}')

print('\n' + '='*60)
print('CURRENT SNAPSHOT')
print('='*60)
print(f'Targets: {cur.get_targets()}')
print(f'include_superseded: {cur.include_superseded}')
for b in cur.behaviors:
    print(f'  {b.target}: cred={b.credibility:.2f}, state={b.state}')

print('\n' + '='*60)
print('RUNNING INDIVIDUAL DETECTORS')
print('='*60)

# Test each detector individually
print('\n--- TopicEmergenceDetector ---')
emergence = TopicEmergenceDetector()
emergence_signals = emergence.detect(ref, cur)
print(f'Signals: {len(emergence_signals)}')
for s in emergence_signals:
    print(f'  {s.drift_type.value}: {s.affected_targets} (score={s.drift_score:.2f})')

print('\n--- TopicAbandonmentDetector ---')
abandonment = TopicAbandonmentDetector()
abandon_signals = abandonment.detect(ref, cur)
print(f'Signals: {len(abandon_signals)}')
for s in abandon_signals:
    print(f'  {s.drift_type.value}: {s.affected_targets} (score={s.drift_score:.2f})')

print('\n--- IntensityShiftDetector ---')
intensity = IntensityShiftDetector()
intensity_signals = intensity.detect(ref, cur)
print(f'Signals: {len(intensity_signals)}')
for s in intensity_signals:
    print(f'  {s.drift_type.value}: {s.affected_targets} (score={s.drift_score:.2f})')

print('\n--- PreferenceReversalDetector ---')
reversal = PreferenceReversalDetector()
reversal_signals = reversal.detect(ref, cur)
print(f'Signals: {len(reversal_signals)}')
for s in reversal_signals:
    print(f'  {s.drift_type.value}: {s.affected_targets} (score={s.drift_score:.2f})')

print('\n' + '='*60)
print('FULL DRIFT DETECTION (with debug)')
print('='*60)

import logging
logging.basicConfig(level=logging.INFO)

detector = DriftDetector()
# Bypass cooldown for testing
detector.settings.scan_cooldown_seconds = 0

print(f'Settings threshold: {detector.settings.drift_score_threshold}')
print(f'Settings min_behaviors: {detector.settings.min_behaviors_for_drift}')
print(f'Settings cooldown: {detector.settings.scan_cooldown_seconds}s (bypassed for testing)')
print(f'Num detectors: {len(detector.detectors)}')

events = detector.detect_drift('user_test_001')
print(f'\nDetected {len(events)} events:')
for e in events:
    print(f'  - {e.drift_type.value}: {e.affected_targets} (score: {e.drift_score:.2f})')
    print(f'    Evidence: {e.evidence}')
