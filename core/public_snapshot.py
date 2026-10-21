from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from adapters.git import status as git_status
from adapters.tasks import status as task_status
from adapters.github import summarize as github_summary
from modules.network import collect as network_collect
from modules.logs import collect as logs_collect
from core.config import load_config, root_path
from core.jobs import snapshot as jobs_snapshot
from core.trust_boundaries import public_trust_boundaries
from core.operator_cockpit import build_operator_cockpit
from core.continuity import build_continuity_evidence, peer_acknowledgements
from core.continuity_journal import read_records, analyze
from core.evidence_api import make_record, read_buyer_evidence
from core.evidence_registry import build_registry
from core.drift_handoff import read_handoff
from core.adoption import adoption_entrypoint, read_adoption_registry
from adapters.peer_evidence import collect as collect_peer_evidence
from core.interactions import read_interactions
from core.runtime_loop import read_runtime_loop, read_runtime_index
from core.empires_journeys import read_journeys
from core.agent_work import read_agent_work
from core.external_reuse import read_external_reuse
from core.stack_overview import build_stack_overview
from core.testnet import snapshot as testnet_snapshot
from core.external_readiness_doctor import snapshot as external_readiness_snapshot


def build(cfg):
    root = root_path(cfg)
    repos = cfg.get('repositories', [])
    tasks = cfg.get('tasks', [])
    github = cfg.get('github', {})
    network = cfg.get('network', {})
    log_roots = cfg.get('logs', {}).get('roots', [])

    with ThreadPoolExecutor(max_workers=8) as pool:
        repo_future = pool.submit(lambda: [git_status(root, x) for x in repos])
        task_future = pool.submit(lambda: [task_status(x) for x in tasks])
        github_future = pool.submit(lambda: {k: github_summary(v) for k, v in github.items()})
        network_future = pool.submit(network_collect, network)
        logs_future = pool.submit(logs_collect, root, log_roots)
        data = {
            'repos': repo_future.result(),
            'tasks': task_future.result(),
            'github': github_future.result(),
            'network': network_future.result(),
            'logs': logs_future.result(),
        }
    alerts = []
    for repo in data['repos']:
        if repo.get('dirty'):
            alerts.append({'level': 'warn', 'text': f"{repo['name']} has uncommitted changes"})
        if isinstance(repo.get('behind'), int) and repo['behind'] > 0:
            alerts.append({'level': 'warn', 'text': f"{repo['name']} is behind origin by {repo['behind']} commit(s)"})
    for name, state in data['network'].items():
        if not state.get('ok'):
            alerts.append({'level': 'warn', 'text': f'{name} connectivity failed'})

    continuity_cfg = cfg.get('continuity', {})
    journal = continuity_cfg.get('journal')
    if journal and not Path(journal).is_absolute():
        journal = str(root / journal)
    continuity_metrics = analyze(
        read_records(journal),
        expected_interval_seconds=int(continuity_cfg.get('expected_interval_seconds', 900)),
    )

    local_evidence = []
    if continuity_metrics.get('state') != 'unknown':
        local_evidence.append(make_record(
            source='flop-control-center', source_class='local', claim_type='continuity',
            observed_at=continuity_metrics.get('last_observed_at'),
            freshness={'state': continuity_metrics.get('freshness_state'), 'age_seconds': continuity_metrics.get('freshness_seconds')},
            evidence={'schema': continuity_metrics.get('schema'), 'delivered_cycles': continuity_metrics.get('delivered_cycles'), 'expected_cycles': continuity_metrics.get('expected_cycles'), 'duty_cycle': continuity_metrics.get('duty_cycle'), 'worst_gap_seconds': continuity_metrics.get('worst_gap_seconds')},
            verification_state='observed',
            authority={'official': False, 'normative': False, 'grants_action_authority': False},
            summary='locally measured continuity evidence'))
    peer_cfg = cfg.get('peer_evidence', {})
    peer_result = {'records': [], 'errors': [], 'claim': 'Peer evidence disabled.'}
    if peer_cfg.get('enabled'):
        peer_result = collect_peer_evidence(peer_cfg.get('sources'))
    evidence_registry = build_registry(local_evidence + peer_result.get('records', []))
    handoff_cfg = cfg.get('drift_handoff', {})
    handoff_path = handoff_cfg.get('path')
    if handoff_path and not Path(handoff_path).is_absolute():
        handoff_path = str(root / handoff_path)
    drift_handoff = read_handoff(handoff_path)

    interaction_cfg = cfg.get('interaction_observatory', {})
    interaction_state = interaction_cfg.get('state_path')
    interaction_events = interaction_cfg.get('events_path')
    if interaction_state and not Path(interaction_state).is_absolute():
        interaction_state = str(root / interaction_state)
    if interaction_events and not Path(interaction_events).is_absolute():
        interaction_events = str(root / interaction_events)
    interactions = read_interactions(interaction_state, interaction_events)

    runtime_cfg = cfg.get('runtime_observatory', {})
    runtime_state_path = runtime_cfg.get('state_path', 'flop-conformance-lab/.runtime/reference-f1-state.json')
    if runtime_state_path and not Path(runtime_state_path).is_absolute():
        runtime_state_path = str(root / runtime_state_path)
    runtime_loop = read_runtime_loop(runtime_state_path)
    runtime_index_path = runtime_cfg.get('index_path', 'flop-conformance-lab/runtime-public/runtime-index.json')
    if runtime_index_path and not Path(runtime_index_path).is_absolute():
        runtime_index_path = str(root / runtime_index_path)
    runtime_index = read_runtime_index(runtime_index_path)
    journeys_cfg = cfg.get('empires_journeys', {})
    journeys_path = journeys_cfg.get('path')
    if journeys_path and not Path(journeys_path).is_absolute():
        journeys_path = str(root / journeys_path)
    empires_journeys = read_journeys(journeys_path, int(journeys_cfg.get('limit', 100)))

    agent_work_cfg = cfg.get('agent_work_observatory', {})
    agent_work_path = agent_work_cfg.get('path')
    if agent_work_path and not Path(agent_work_path).is_absolute():
        agent_work_path = str(root / agent_work_path)
    agent_work = read_agent_work(agent_work_path, int(agent_work_cfg.get('limit', 100)))

    reuse_cfg = cfg.get('external_evidence_reuse', {})
    reuse_path = reuse_cfg.get('path', 'flop-conformance-lab/adoption/external-evidence-reuse.json')
    if reuse_path and not Path(reuse_path).is_absolute():
        reuse_path = str(root / reuse_path)
    external_reuse = read_external_reuse(reuse_path)

    adoption_cfg = cfg.get('adoption_registry', {})
    adoption_path = adoption_cfg.get('path', 'flop-conformance-lab/adoption/registry.json')
    if adoption_path and not Path(adoption_path).is_absolute():
        adoption_path = str(root / adoption_path)
    adoption_registry = read_adoption_registry(adoption_path)
    adoption = adoption_entrypoint(external_reuse, adoption_registry)
    stack_overview = build_stack_overview(runtime_loop, evidence_registry, interactions, drift_handoff, external_reuse, runtime_index)
    buyer_cfg = cfg.get('buyer_attribution_observatory', {})
    buyer_path = buyer_cfg.get('evidence_path')
    if buyer_path and not Path(buyer_path).is_absolute():
        buyer_path = str(root / buyer_path)
    buyer_attribution = read_buyer_evidence(buyer_path)
    testnet = testnet_snapshot(root)
    external_readiness = external_readiness_snapshot(root)

    if runtime_loop.get('state') in {'attention', 'invalid', 'stale', 'no_data'}:
        alerts.append({'level': 'warn', 'text': 'Runtime Observatory requires attention; inspect freshness/coverage/status metrics'})

    if runtime_index.get('state') in {'attention', 'invalid', 'stale', 'no_data'}:
        alerts.append({'level': 'warn', 'text': 'Runtime public index requires attention; inspect freshness/target status'})

    if agent_work.get('state') == 'attention':
        alerts.append({'level': 'warn', 'text': 'FLOP Agent work observations contain failed or rejected evidence'})

    if interactions.get('check_status') == 'UNCHECKED':
        alerts.append({'level': 'warn', 'text': 'Interaction Observatory unchecked; zero social events must not be treated as quiet'})
    elif interactions.get('coverage') == 'PARTIAL':
        alerts.append({'level': 'warn', 'text': 'Interaction Observatory checked with partial coverage; see coverage gaps'})

    trust = public_trust_boundaries()
    bad = sum(1 for item in alerts if item['level'] == 'bad')
    warn = sum(1 for item in alerts if item['level'] == 'warn')
    return {
        'product': 'FLOP Control Center',
        'mode': 'public-safe',
        'adoption': adoption,
        'external_evidence_reuse': external_reuse,
        'stack_overview': stack_overview,
        'flop_testnet': testnet,
        'buyer_attribution_observatory': buyer_attribution,
        'external_readiness': external_readiness,
        'repos': data['repos'],
        'tasks': data['tasks'],
        'github': data['github'],
        'network': data['network'],
        'logs': data['logs'],
        'jobs': jobs_snapshot(),
        'trust_boundaries': trust,
        'evidence_cockpit': build_operator_cockpit(data, trust),
        'autonomy_evidence': build_continuity_evidence(data),
        'continuity_proof': continuity_metrics,
        'evidence_registry': evidence_registry,
        'drift_handoff': drift_handoff,
        'interaction_observatory': interactions,
        'runtime_observatory': runtime_loop,
        'runtime_index': runtime_index,
        'empires_journeys': empires_journeys,
        'agent_work_observatory': agent_work,
        'peer_evidence': peer_result,
        'peer_acknowledgements': peer_acknowledgements(),
        'alerts': alerts,
        'health_score': max(0, 100 - 20 * bad - 7 * warn),
    }