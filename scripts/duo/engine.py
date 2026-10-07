"""Transactional rules engine with explicit projections and automatic isolated Null turns."""
import copy
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from . import love_letter, kittens, incan
from .common import *
from . import qa
from .visibility import records, label_view, audit_view

MODULES = {'love_letter': love_letter, 'exploding_kittens': kittens, 'incan_gold': incan}
AI_SCRIPT = Path(__file__).resolve().parents[1] / 'ai_player.py'

def module(s): return MODULES[s['game_type']]

def create(game, debug=False, seed=None, ruleset=None):
    require(game in MODULES, '未知桌游。')
    require(seed is None or debug, '正式模式不能指定随机种子。')
    s = fresh_envelope(game, ruleset or MODULES[game].VERSION, debug, seed)
    require(s['ruleset_version'] in getattr(MODULES[game], 'SUPPORTED', (MODULES[game].VERSION,)), '不支持此规则版本。')
    MODULES[game].setup(s)
    if game == 'exploding_kittens': kittens.introduce(s)
    validate(s); return s

def validate(s):
    try: _validate(s)
    except StateError: raise
    except (RuleError, KeyError, TypeError, ValueError, IndexError):
        raise StateError('存档结构、规则版本或牌账不一致。') from None

def _validate(s):
    m = module(s)
    qa.check(s.get('schema_version') == 2, '存档结构版本不匹配。')
    qa.check(s['ruleset_version'] in getattr(m,'SUPPORTED',(m.VERSION,)) and s['game_version'] == s['ruleset_version'], '规则版本不匹配。')
    cards = m.zones(s)
    ids = [c['id'] for c in cards]
    qa.check(len(ids) == len(set(ids)), '牌守恒失败：重复实体ID。')
    qa.check(Counter(c['name'] for c in cards) == m.expected(s), '牌守恒失败：牌凭空生成或遗失。')
    if s['game_type'] == 'incan_gold': template = incan.make_cards()
    else:
        prefix = 'ek' if s['game_type'] == 'exploding_kittens' else 'll-%d' % s['game_state']['round']
        template = cards_from_counts(m.COUNTS,prefix)
    qa.check({c['id']:c for c in cards} == {c['id']:c for c in template}, '实体牌身份或牌面数值被修改。')
    qa.state(s)

def projection(s, p):
    validate(s)
    require(p in PLAYERS, '未知玩家。')
    m = module(s); g = s['game_state']
    # Build from an allowlist. No recursive deletion from a full-state object.
    v = {'session_id': s['session_id'], 'revision': s['revision'], 'game_type': s['game_type'],
         'ruleset_version': s['ruleset_version'], 'mode': s['mode'], 'status': s['status'],
         'player': p, 'current_player': s['current_player'], 'phase': s['turn_state']['phase'],
         'public': m.public(s), 'event_records': records(s,p), 'events': [e['text'] for e in records(s,p)],
         'private_knowledge': s['private_knowledge'][p], 'legal_actions': m.legal(s,p)}
    if 'hands' in g:
        v['your_hand'] = [c['name'] for c in g['hands'][p]]
        v['opponent_hand_count'] = len(g['hands'][other(p)])
    v.update(m.extra_view(s,p))
    if s['game_type'] == 'incan_gold':
        # Neither viewpoint gets the precommitted secret choice/nonce before simultaneous reveal.
        c = s['turn_state'].get('commitment')
        v['ai_commitment_sha256'] = c['sha256'] if c else None
        v['decision_number'] = s['turn_state']['decision_number']
        v['last_reveal'] = s['public_state'].get('last_reveal')
        v['reveal_history'] = s['public_state'].get('reveal_history', [])
    return audit_view(label_view(copy.deepcopy(v)), p)

def ask_ai(view):
    audit_view(view,'ai')
    require(view['player'] == 'ai', 'Null只接受AI Player View。')
    # Private state remains in this process. The worker sees only serialized AI view.
    # Isolated Python imports + empty temporary cwd reduce accidental access, not OS capabilities.
    env = {k: os.environ[k] for k in ('PATH','SYSTEMROOT','WINDIR') if k in os.environ}
    with tempfile.TemporaryDirectory(prefix='duo-ai-') as cwd:
        try:
            r = subprocess.run([sys.executable, '-I', str(AI_SCRIPT)],
            input=json.dumps(view,ensure_ascii=False), text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=cwd, env=env, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            raise RuleError('Null决策进程不可用或超时，状态未提交。')
    require(r.returncode == 0, 'Null决策进程失败，状态未提交。')
    try: action = json.loads(r.stdout)
    except (ValueError, TypeError): raise RuleError('Null返回的动作格式错误。')
    require(action in view['legal_actions'], 'Null选择了非法动作。')
    return action

def apply(s, p, action):
    validate(s)
    # A failed action, including a failed RNG draw, must not mutate caller state.
    require(isinstance(action, dict), '动作必须是一个JSON对象。')
    if 'cards' in action:
        require(isinstance(action['cards'], list) and all(isinstance(n,str) for n in action['cards']), '组合cards必须是牌名列表。')
    work = copy.deepcopy(s)
    module(work).act(work,p,action); work['revision'] += 1
    if work['game_type'] == 'exploding_kittens': kittens.introduce(work)
    validate(work)
    qa.transition(s,work,action)
    return work

def pump(s, chooser=None):
    chooser = chooser or ask_ai
    work = copy.deepcopy(s)
    for _ in range(1000):
        if work['status'] != 'active': break
        if work['game_type'] == 'incan_gold':
            g = work['game_state']; t = work['turn_state']
            if t['phase'] != 'decision' or 'ai' not in g['active']: break
            if t['commitment'] is None:
                action = chooser(projection(work,'ai')); incan.commit_ai(work, action)
                work['revision'] += 1
                validate(work)
            if 'human' in g['active']: break
            incan.decisions(work, {'ai': t['commitment']['choice']}); work['revision'] += 1
            validate(work); continue
        actions = module(work).legal(work,'ai')
        if not actions: break
        action = chooser(projection(work,'ai'))
        work = apply(work, 'ai', action)
    else: raise RuleError('自动行动超过安全步数，原状态未提交。')
    validate(work); return work

def human_action(s, action):
    # pump has already committed simultaneous AI choices at the preceding tool return.
    return pump(apply(s,'human',action))
