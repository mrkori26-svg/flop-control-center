import json
from datetime import datetime, timezone
from pathlib import Path

def snapshot(root):
    source = Path(root) / 'useful-work-operator' / 'ecosystem' / 'ecosystem-status.json'
    if not source.exists():
        return {
            'schema':'flop.control-center-ecosystem/v1',
            'state':'missing',
            'source':str(source),
            'opportunities':[],
            'programs':{}
        }
    try:
        data = json.loads(source.read_text(encoding='utf-8'))
    except Exception as exc:
        return {
            'schema':'flop.control-center-ecosystem/v1',
            'state':'invalid',
            'error':str(exc),
            'source':str(source)
        }
    harness_tracker_path = Path(root) / 'useful-work-operator' / 'ecosystem' / 'harness' / 'state' / 'tracker-status.json'
    harness_prepared_path = Path(root) / 'useful-work-operator' / 'ecosystem' / 'harness' / 'state' / 'prepared.json'
    harness_qualification_path = Path(root) / 'useful-work-operator' / 'ecosystem' / 'harness' / 'state' / 'qualification.json'
    harness_portfolio_path = Path(root) / 'useful-work-operator' / 'ecosystem' / 'harness' / 'state' / 'portfolio.json'
    harness_pr_health_path = Path(root) / 'useful-work-operator' / 'ecosystem' / 'harness' / 'state' / 'pr-health.json'
    harness_portfolio_daemon_path = Path(root) / 'useful-work-operator' / 'ecosystem' / 'harness' / 'state' / 'portfolio-daemon.json'
    ecosystem_supervisor_path = Path(root) / 'useful-work-operator' / 'ecosystem' / 'ecosystem-supervisor-heartbeat.json'
    block_lane_paths = [
        Path(root) / 'useful-work-operator' / 'state-blockrewards-0-of-2' / 'status.json',
        Path(root) / 'useful-work-operator' / 'state-blockrewards-1-of-2' / 'status.json',
    ]
    try:
        harness_tracker = json.loads(harness_tracker_path.read_text(encoding='utf-8')) if harness_tracker_path.exists() else None
    except Exception:
        harness_tracker = {'state':'invalid'}
    try:
        harness_prepared = json.loads(harness_prepared_path.read_text(encoding='utf-8')) if harness_prepared_path.exists() else None
    except Exception:
        harness_prepared = {'state':'invalid'}
    try:
        harness_qualification = json.loads(harness_qualification_path.read_text(encoding='utf-8')) if harness_qualification_path.exists() else None
    except Exception:
        harness_qualification = {'state':'invalid'}
    try:
        harness_portfolio = json.loads(harness_portfolio_path.read_text(encoding='utf-8')) if harness_portfolio_path.exists() else None
    except Exception:
        harness_portfolio = {'state':'invalid'}
    try:
        harness_pr_health = json.loads(harness_pr_health_path.read_text(encoding='utf-8')) if harness_pr_health_path.exists() else None
    except Exception:
        harness_pr_health = {'state':'invalid'}
    try:
        harness_portfolio_daemon = json.loads(harness_portfolio_daemon_path.read_text(encoding='utf-8')) if harness_portfolio_daemon_path.exists() else None
    except Exception:
        harness_portfolio_daemon = {'state':'invalid'}
    try:
        ecosystem_supervisor = json.loads(ecosystem_supervisor_path.read_text(encoding='utf-8')) if ecosystem_supervisor_path.exists() else None
    except Exception:
        ecosystem_supervisor = {'state':'invalid'}
    if ecosystem_supervisor is None:
        supervisor_health = {'state':'missing','path':str(ecosystem_supervisor_path)}
    elif ecosystem_supervisor.get('state') == 'invalid':
        supervisor_health = {'state':'invalid','path':str(ecosystem_supervisor_path)}
    else:
        try:
            observed = datetime.fromisoformat(str(ecosystem_supervisor.get('at','')).replace('Z','+00:00'))
            age_seconds = max(0.0, (datetime.now(timezone.utc) - observed).total_seconds())
            state = 'healthy' if ecosystem_supervisor.get('healthy') is True and age_seconds <= 180 else ('stale' if age_seconds > 180 else 'degraded')
            supervisor_health = {'state':state,'age_seconds':round(age_seconds,3),'heartbeat':ecosystem_supervisor}
        except Exception:
            supervisor_health = {'state':'invalid','path':str(ecosystem_supervisor_path)}
    block_lanes = []
    for lane_path in block_lane_paths:
        try:
            block_lanes.append(json.loads(lane_path.read_text(encoding='utf-8')) if lane_path.exists() else {'state':'missing','path':str(lane_path)})
        except Exception:
            block_lanes.append({'state':'invalid','path':str(lane_path)})
    return {
        'schema':'flop.control-center-ecosystem/v1',
        'state':'ready',
        'generatedAt':data.get('generatedAt'),
        'counts':data.get('counts',{}),
        'programs':data.get('programs',{}),
        'top_opportunities':data.get('opportunities',[])[:50],
        'interesting_rooms':data.get('discovery',{}).get('interestingRooms',[])[:100],
        'supervisor':supervisor_health,
        'blockrewards':{
            'lanes':block_lanes,
            'precision_policy':'qualification mode: deterministic/local verification only; deterministic validation at confidence 1 is allowed after local output-contract validation; creative and model-consensus jobs remain quarantined; fail closed',
        },
        'harness':{
            'tracker':harness_tracker,
            'prepared':harness_prepared,
            'qualification':harness_qualification,
            'portfolio':harness_portfolio,
            'portfolio_daemon':harness_portfolio_daemon,
            'pr_health':harness_pr_health,
        },
        'claim_boundary':'Discovery and ranking are observations; execution is performed by program-specific workers.'
    }
