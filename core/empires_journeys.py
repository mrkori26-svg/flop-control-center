import json
from pathlib import Path

def read_journeys(path, limit=100):
    if not path:
        return {'schema':'flop.empires-journey-index.v1','state':'disabled','journeys':[]}
    root = Path(path)
    if not root.exists():
        return {'schema':'flop.empires-journey-index.v1','state':'missing','journeys':[]}
    files = [root] if root.is_file() else sorted((f for f in root.glob('*.json') if not f.name.endswith(('.report.json','.work-receipt.json'))), reverse=True)
    rows, rejected = [], []
    for file in files[:limit]:
        try:
            value = json.loads(file.read_text(encoding='utf-8'))
            if value.get('schema') != 'flop-empires-journey-evidence/v1':
                raise ValueError('schema mismatch')
            verification = value.get('verification') or {}
            report_path = file.with_name(file.stem + '.report.json')
            conformance = None
            if report_path.exists():
                report = json.loads(report_path.read_text(encoding='utf-8'))
                if report.get('schema') == 'flop-conformance-result/v1':
                    conformance = {
                        'result': report.get('result'),
                        'summary': report.get('summary'),
                        'profile': report.get('profile'),
                    }
            rows.append({
                'journey_id': value.get('journey_id'),
                'capability': value.get('capability'),
                'actor_did': value.get('actor_did'),
                'request_id': value.get('request_id'),
                'event_seq': (value.get('transition') or {}).get('event_seq'),
                'verified': bool(verification) and all(verification.values()),
                'verification': verification,
                'semantic_digest': value.get('semantic_digest'),
                'conformance': conformance,
                'source': str(file),
            })
        except Exception as exc:
            rejected.append({'source':str(file),'error':str(exc)})
    return {
        'schema':'flop.empires-journey-index.v1',
        'state':'observed',
        'journeys':rows,
        'rejected':rejected,
        'claim':'Operational index only; conformance remains the Lab responsibility.',
    }

def find_journey(path, journey_id):
    if not path or not journey_id:
        return None
    root = Path(path)
    files = [root] if root.is_file() else list(root.glob('*.json')) if root.exists() else []
    for file in files:
        try:
            value = json.loads(file.read_text(encoding='utf-8'))
            if value.get('schema') == 'flop-empires-journey-evidence/v1' and value.get('journey_id') == journey_id:
                return value
        except Exception:
            continue
    return None
