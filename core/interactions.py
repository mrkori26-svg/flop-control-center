import json
from pathlib import Path

STATE_SCHEMA = 'flop.interaction-state.v1'
EVENTS_SCHEMA = 'flop.interaction-events.v1'


def _read(path):
    p = Path(path)
    if not p.exists():
        return None, 'missing'
    try:
        return json.loads(p.read_text(encoding='utf-8')), None
    except Exception:
        return None, 'invalid'


def read_interactions(state_path=None, events_path=None):
    if not state_path:
        return {
            'schema': STATE_SCHEMA,
            'state': 'disabled',
            'check_status': 'UNCHECKED',
            'coverage': 'PARTIAL',
            'coverage_gaps': [],
            'events': [],
            'threads': [],
            'claim': 'Interaction Observatory not configured.',
        }

    state, err = _read(state_path)
    if err:
        return {
            'schema': STATE_SCHEMA,
            'state': err,
            'check_status': 'UNCHECKED',
            'events': [],
            'threads': [],
            'claim': 'Interaction state unavailable. Zero events must not be interpreted as quiet.',
        }
    if state.get('schema') != STATE_SCHEMA or not isinstance(state.get('threads'), list):
        return {
            'schema': STATE_SCHEMA,
            'state': 'invalid',
            'check_status': 'UNCHECKED',
            'events': [],
            'threads': [],
            'claim': 'Interaction state failed schema validation.',
        }

    events = []
    if events_path:
        payload, event_err = _read(events_path)
        if not event_err and payload.get('schema') == EVENTS_SCHEMA and isinstance(payload.get('events'), list):
            events = payload['events']

    checked = state.get('checkStatus') == 'CHECKED'
    counts = {}
    for event in events:
        kind = str(event.get('kind') or 'UNKNOWN')
        counts[kind] = counts.get(kind, 0) + 1

    actionable = [
        event for event in events
        if event.get('action') in {'RUN_CONFORMANCE', 'INSPECT_ADOPTION'}
    ]
    return {
        'schema': STATE_SCHEMA,
        'state': 'observed' if checked else 'unchecked',
        'check_status': 'CHECKED' if checked else 'UNCHECKED',
        'generated_at': state.get('generatedAt'),
        'coverage': state.get('coverage') if state.get('coverage') in {'FULL', 'PARTIAL'} else 'PARTIAL',
        'coverage_gaps': state.get('coverageGaps', []),
        'errors': state.get('errors', []),
        'threads': state.get('threads', []),
        'events': events,
        'counts': counts,
        'actionable': actionable,
        'claim': (
            ('Checked interaction state. Zero events means quiet for the checked coverage; some optional sources were unavailable.'
             if state.get('coverage') == 'PARTIAL'
             else 'Checked interaction state. Zero events means quiet for this observation window.')
            if checked else
            'Observation did not complete. Zero events is not evidence of quiet.'
        ),
    }
