"""Numbered artifacts; v2 random entry, v1 ordered-entry saves retain their rules."""
from collections import Counter
from .common import *

LEGACY_VERSION = 'incan-gold-egg-2018-numbered-artifacts-2p-adaptation-v1'
VERSION = 'incan-gold-numbered-artifacts-random-entry-2p-v2'
SUPPORTED = (LEGACY_VERSION, VERSION)
TREASURES = [1, 2, 3, 4, 5, 5, 7, 7, 9, 11, 11, 13, 14, 15, 17]
HAZARDS = ('Spiders', 'Mummies', 'Fire', 'Snakes', 'Rockfall')
ARTIFACTS = [5, 7, 8, 10, 12]
LABEL = {'Spiders': '蜘蛛', 'Mummies': '木乃伊', 'Fire': '火焰', 'Snakes': '蛇', 'Rockfall': '落石'}

def make_cards():
    cards = [{'id': 'ig-t-%d' % i, 'name': 'Treasure', 'value': v} for i, v in enumerate(TREASURES)]
    cards += [{'id': 'ig-h-%s-%d' % (h, i), 'name': h} for h in HAZARDS for i in range(3)]
    cards += [{'id': 'ig-a-%d' % v, 'name': 'Artifact', 'value': v} for v in ARTIFACTS]
    return cards

def setup(s):
    s['game_state'] = {'round': 0, 'bank': {p: 0 for p in PLAYERS},
                       'artifacts': {p: [] for p in PLAYERS}, 'removed': [], 'path': [],
                       'deck': make_cards()[:30], 'future_artifacts': make_cards()[30:],
                       'hazards': {}, 'loot': {p: 0 for p in PLAYERS}, 'active': list(PLAYERS), 'path_gems': 0}
    if s['ruleset_version'] == VERSION:
        Randomness(s['randomness_state']).shuffle(s['game_state']['future_artifacts'])
    event(s, '印加宝藏：编号遗物按牌面5/7/8/10/12计分，%s加入，五轮；双人适配（官方3–8人）。' %
          ('随机顺序' if s['ruleset_version'] == VERSION else '按轮序'))
    new_round(s)

def new_round(s):
    g = s['game_state']; g['round'] += 1
    g['deck'].append(g['future_artifacts'].pop(0))
    Randomness(s['randomness_state']).shuffle(g['deck'])
    g.update(active=list(PLAYERS), loot={p: 0 for p in PLAYERS}, path_gems=0, path=[], hazards={})
    s['turn_state'] = {'phase': 'reveal', 'commitment': None, 'decision_number': 0}
    s['current_player'] = 'simultaneous'
    # The joining artifact remains face down; its value is not announced before reveal.
    event(s, '第%d轮探险，秘密加入一张遗物。' % g['round'])
    reveal(s)

def end_round(s, hazard=None):
    g = s['game_state']
    for c in g['path']:
        if c['id'] == hazard or c['name'] == 'Artifact': g['removed'].append(c)
        else: g['deck'].append(c)
    g['path'] = []; g['path_gems'] = 0
    g['active'] = []; g['loot'] = {p: 0 for p in PLAYERS}
    s['turn_state']['commitment'] = None
    if g['round'] == 5:
        s['status'] = 'finished'; s['turn_state']['phase'] = 'finished'
        scores = {p: g['bank'][p] + sum(c['value'] for c in g['artifacts'][p]) for p in PLAYERS}
        best = max(scores.values()); winners = [p for p in PLAYERS if scores[p] == best]
        if len(winners) == 2:
            count = max(len(g['artifacts'][p]) for p in PLAYERS)
            winners = [p for p in PLAYERS if len(g['artifacts'][p]) == count]
        g['scores'] = scores; g['winners'] = winners
        event(s, '五轮结束：你 %d，Null %d；获胜：%s。' %
              (scores['human'], scores['ai'], '、'.join(NAMES[p] for p in winners)))
    else:
        s['turn_state']['phase'] = 'round_end'
        event(s, '本轮探险结束。准备好后说“下一轮”。')

def reveal(s):
    g = s['game_state']
    require(g['deck'], '牌堆为空：存档异常。')
    c = g['deck'].pop(0); g['path'].append(c)
    if c['name'] == 'Treasure':
        share, rest = divmod(c['value'], len(g['active']))
        for p in g['active']: g['loot'][p] += share
        g['path_gems'] += rest
        event(s, '火把照亮石室：发现%d颗宝石，在场每人获得%d颗，%d颗留在路径。' % (c['value'], share, rest))
    elif c['name'] == 'Artifact':
        event(s, '尘土下露出价值%d的遗物，留在路径等待独自撤退者领取。' % c['value'])
    else:
        g['hazards'][c['name']] = g['hazards'].get(c['name'], 0)+1
        event(s, '前方出现%s（第%d张）。' % (LABEL[c['name']], g['hazards'][c['name']]))
        if g['hazards'][c['name']] == 2:
            event(s, '重复危险！仍在遗迹的人失去本轮未带回财富，第二张危险永久移除。')
            end_round(s, c['id']); return
    s['turn_state']['phase'] = 'decision'
    s['turn_state']['decision_number'] += 1
    s['turn_state']['commitment'] = None

def legal(s, p):
    if s['status'] != 'active': return []
    phase = s['turn_state']['phase']; g = s['game_state']
    if phase == 'round_end': return [{'type': 'next_round'}] if p == 'human' else []
    if phase != 'decision' or p not in g['active']: return []
    return [{'type': 'continue'}, {'type': 'return'}]

def commit_ai(s, action):
    """Called before reading/parsing a human decision. No choice revealed until resolution."""
    import hashlib, secrets
    require(action in legal(s, 'ai'), 'AI选择不合法。')
    require(s['turn_state']['commitment'] is None, 'AI选择已经锁定。')
    nonce = secrets.token_hex(24)
    payload = '%s:%d:%d:%s:%s' % (s['session_id'], s['game_state']['round'],
              s['turn_state']['decision_number'], action['type'], nonce)
    s['turn_state']['commitment'] = {'choice': action['type'], 'nonce': nonce,
                                    'sha256': hashlib.sha256(payload.encode()).hexdigest()}

def decisions(s, choices):
    g = s['game_state']; t = s['turn_state']; commitment = t['commitment']
    from .qa import check, commitment as verify_commitment
    check(set(choices) == set(g['active']), '同步决策缺少探险者。')
    if 'ai' in g['active']:
        check(commitment is not None, 'Null决策未提前保存。')
        verify_commitment(s,commitment)
        check(choices['ai'] == commitment['choice'], 'Null选择与已保存承诺不符。')
    event(s, '同时揭晓：' + '；'.join('%s选择%s' % (NAMES[p], '继续' if choices[p] == 'continue' else '返回营地') for p in g['active']))
    if commitment:
        # Published proof allows the user to check that the AI decision was fixed previously.
        proof = {'choice': commitment['choice'], 'nonce': commitment['nonce'],
            'sha256': commitment['sha256'], 'session_id': s['session_id'],
            'round': g['round'], 'decision_number': t['decision_number']}
        s['public_state'].setdefault('reveal_history', []).append(proof)
        if 'human' in g['active']:
            s['public_state']['last_reveal'] = proof
    t['commitment'] = None
    leavers = [p for p in g['active'] if choices[p] == 'return']
    if leavers:
        share, g['path_gems'] = divmod(g['path_gems'], len(leavers))
        for p in leavers:
            gain = g['loot'][p] + share; g['bank'][p] += gain; g['loot'][p] = 0
            event(s, '%s安全带回%d颗宝石。' % (NAMES[p], gain))
        if len(leavers) == 1:
            artifacts = [c for c in g['path'] if c['name'] == 'Artifact']
            g['artifacts'][leavers[0]].extend(artifacts)
            g['path'] = [c for c in g['path'] if c['name'] != 'Artifact']
            if artifacts: event(s, '%s独自撤退，获得路径全部遗物。' % NAMES[leavers[0]])
        elif any(c['name'] == 'Artifact' for c in g['path']):
            event(s, '双方同时返回，无人拿到路径遗物。')
        g['active'] = [p for p in g['active'] if p not in leavers]
    if not g['active']: end_round(s)
    else: reveal(s)

def act(s, p, a):
    require(a in legal(s, p), '行动不合法：只能在决策阶段继续/返回，或在轮间开始下一轮。')
    if a['type'] == 'next_round': new_round(s); return
    if p == 'ai': raise RuleError('AI同步选择必须先通过commit_ai锁定，不能事后输入。')
    g = s['game_state']; choices = {p: a['type']}
    if 'ai' in g['active']:
        require(s['turn_state']['commitment'] is not None, 'AI尚未锁定选择，不能提交人类选择。')
        choices['ai'] = s['turn_state']['commitment']['choice']
    decisions(s, choices)

def public(s):
    g = s['game_state']; result = {'round': g['round'], 'active': list(g['active']),
        'loot': dict(g['loot']), 'path_gems': g['path_gems'], 'path': [{k: v for k, v in c.items() if k != 'id'} for c in g['path']],
        'hazards': dict(g['hazards']), 'deck_count': len(g['deck']),
        'artifacts': {p: [c['value'] for c in g['artifacts'][p]] for p in PLAYERS},
        'removed': [{k: v for k, v in c.items() if k != 'id'} for c in g['removed']]}
    if s['status'] == 'finished': result['scores'] = dict(g['scores'])
    # Tent totals are private; a player can infer them from public history, but no engine oracle.
    return result

def extra_view(s, p):
    g = s['game_state']
    return {'your_bank': g['bank'][p], 'your_score': g['bank'][p] + sum(c['value'] for c in g['artifacts'][p])}

def zones(s):
    g = s['game_state']
    return g['deck'] + g['path'] + g['removed'] + g['future_artifacts'] + sum(g['artifacts'].values(), [])

def expected(s): return Counter(c['name'] for c in make_cards())
