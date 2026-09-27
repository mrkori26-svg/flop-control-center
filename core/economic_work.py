import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def snapshot(root: Path):
    base = root / 'runtime' / 'economic-work'
    status = _read_json(base / 'operator-status.json')
    records = []
    journal = base / 'operational-memory.ndjson'
    if journal.exists():
        try:
            for line in journal.read_text(encoding='utf-8').splitlines()[-5000:]:
                try:
                    item = json.loads(line)
                    if item.get('schema') == 'flop.operational-memory/v1':
                        records.append(item)
                except Exception:
                    pass
        except Exception:
            pass
    now = datetime.now(timezone.utc)
    def window(days):
        cutoff = now - timedelta(days=days)
        rows = []
        for item in records:
            try:
                at = datetime.fromisoformat(item.get('at','').replace('Z','+00:00'))
                if at >= cutoff:
                    rows.append(item)
            except Exception:
                pass
        return {
            'records': len(rows),
            'accepted': sum(1 for x in rows if x.get('outcome') == 'ACCEPTED'),
            'completed': sum(1 for x in rows if x.get('outcome') == 'COMPLETED'),
            'validated': sum(1 for x in rows if x.get('outcome') == 'VALIDATED'),
            'failed': sum(1 for x in rows if x.get('outcome') in {'FAILED','EXPIRED'}),
        }
    return {
        'schema': 'flop.control-center-economic-work/v1',
        'observed_at': now.isoformat().replace('+00:00','Z'),
        'status': status if status is not None else {'state':'unknown','reason':'operator status unavailable'},
        'memory': {'d7': window(7), 'd30': window(30), 'd90': window(90)},
        'source': str(base),
        'read_only': True,
    }
