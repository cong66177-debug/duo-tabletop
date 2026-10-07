"""AEG classic 16-card, 2-player, first to seven affection tokens."""
from collections import Counter
from .common import *

VERSION = 'love-letter-aeg-classic16-2016-2p-v1'
COUNTS = {'Guard': 5, 'Priest': 2, 'Baron': 2, 'Handmaid': 2, 'Prince': 2,
          'King': 1, 'Countess': 1, 'Princess': 1}
VALUE = {n: i+1 for i, n in enumerate(COUNTS)}
LABEL = dict(zip(COUNTS, ('卫兵', '牧师', '男爵', '侍女', '王子', '国王', '伯爵夫人', '公主')))

def setup(s):
    s['game_state'] = {'scores': {p: 0 for p in PLAYERS}, 'round': 0, 'goal': 7}
    new_round(s, 'human')

def new_round(s, first):
    g = s['game_state']; g['round'] += 1
    deck = cards_from_counts(COUNTS, 'll-%d' % g['round'])
    Randomness(s['randomness_state']).shuffle(deck)
    g.update(deck=deck, reserve=[deck.pop(0)], removed=[deck.pop(0) for _ in range(3)],
             hands={p: [deck.pop(0)] for p in PLAYERS},
             discards={p: [] for p in PLAYERS}, protected={p: False for p in PLAYERS},
             alive={p: True for p in PLAYERS}, hand_epoch={p: 0 for p in PLAYERS})
    s['private_knowledge'] = {p: [] for p in PLAYERS}
    s['turn_state'] = {'phase': 'play'}
    s['current_player'] = first
    event(s, '情书第 %d 轮开始。公开移除：%s。' %
          (g['round'], '、'.join(LABEL[c['name']] for c in g['removed'])))
    begin_turn(s, first)

def invalidate(s, p):
    g = s['game_state']; g['hand_epoch'][p] += 1
    for viewer in PLAYERS:
        for k in s['private_knowledge'][viewer]:
            if k.get('target') == p and k.get('current'):
                k['current'] = False

def begin_turn(s, p):
    g = s['game_state']; g['protected'][p] = False
    # An opponent now has two cards and may retain either; previous certainty expires.
    invalidate(s, p)
    g['hands'][p].append(g['deck'].pop(0))

def eliminate(s, p):
    g = s['game_state']; g['alive'][p] = False
    g['discards'][p].extend(g['hands'][p]); g['hands'][p] = []
    invalidate(s, p)
    event(s, NAMES[p] + '出局。')

def legal(s, p):
    g = s['game_state']
    if s['status'] != 'active': return []
    if s['turn_state']['phase'] == 'round_end': return [{'type': 'next_round'}] if p == 'human' else []
    if s['current_player'] != p: return []
    names = {c['name'] for c in g['hands'][p]}
    if 'Countess' in names and names & {'Prince', 'King'}: names = {'Countess'}
    actions = []
    q = other(p)
    for name in sorted(names, key=VALUE.get):
        if name in ('Guard', 'Priest', 'Baron', 'King'):
            if g['protected'][q]:
                actions.append({'type': 'play', 'card': name, 'target': None})
            elif name == 'Guard':
                actions.extend({'type': 'play', 'card': name, 'target': q, 'guess': n} for n in COUNTS if n != 'Guard')
            else:
                actions.append({'type': 'play', 'card': name, 'target': q})
        elif name == 'Prince':
            actions.append({'type': 'play', 'card': name, 'target': p})
            if not g['protected'][q]: actions.append({'type': 'play', 'card': name, 'target': q})
        else:
            actions.append({'type': 'play', 'card': name})
    return actions

def finish_round(s):
    g = s['game_state']; survivors = [p for p in PLAYERS if g['alive'][p]]
    if len(survivors) == 1:
        winners = survivors
    else:
        best = max(VALUE[g['hands'][p][0]['name']] for p in survivors)
        winners = [p for p in survivors if VALUE[g['hands'][p][0]['name']] == best]
        if len(winners) > 1:
            totals = {p: sum(VALUE[c['name']] for c in g['discards'][p]) for p in winners}
            winners = [p for p in winners if totals[p] == max(totals.values())]
        event(s, '摊牌：' + '；'.join('%s持%s' % (NAMES[p], LABEL[g['hands'][p][0]['name']]) for p in survivors))
    for p in winners: g['scores'][p] += 1
    g['round_winners'] = winners
    event(s, '本轮获胜：%s。好感：你 %d / Null %d（先到7）。' %
          ('、'.join(NAMES[p] for p in winners), g['scores']['human'], g['scores']['ai']))
    if max(g['scores'].values()) >= g['goal']:
        s['status'] = 'finished'; g['winners'] = winners
    else: s['turn_state'] = {'phase': 'round_end'}

def act(s, p, a):
    require(a in legal(s, p), '行动不合法：检查手牌、目标、卫兵猜牌（不能猜卫兵）和伯爵夫人强制规则。')
    g = s['game_state']
    if a['type'] == 'next_round':
        winners = g['round_winners']; first = Randomness(s['randomness_state']).choose(winners, 'tied-round-first-player') if len(winners) > 1 else winners[0]  # Date tiebreak replaced by program RNG in chat.
        new_round(s, first); return
    name = a['card']; q = a.get('target')
    g['discards'][p].append(take(g['hands'][p], name))
    event(s, '%s打出了%s。' % (NAMES[p], LABEL[name]))
    if name in ('Guard', 'Priest', 'Baron', 'King') and q is None:
        event(s, '对方受到侍女保护，牌效不执行。')
    elif name == 'Guard':
        event(s, '%s猜%s持有%s。' % (NAMES[p], NAMES[q], LABEL[a['guess']]))
        if g['hands'][q][0]['name'] == a['guess']: eliminate(s, q)
        else: event(s, '没有猜中。')
    elif name == 'Priest':
        private(s, p, 'hand', target=q, card=g['hands'][q][0]['name'],
                epoch=g['hand_epoch'][q], current=True, source='Priest')
    elif name == 'Baron':
        v, w = VALUE[g['hands'][p][0]['name']], VALUE[g['hands'][q][0]['name']]
        for viewer, target in ((p,q), (q,p)):
            private(s, viewer, 'hand', target=target, card=g['hands'][target][0]['name'],
                    epoch=g['hand_epoch'][target], current=True, source='Baron')
        if v < w: eliminate(s, p)
        elif w < v: eliminate(s, q)
        else: event(s, '男爵比较平手，双方留在场上。')
    elif name == 'Handmaid': g['protected'][p] = True
    elif name == 'Prince':
        dropped = g['hands'][q].pop(); g['discards'][q].append(dropped)
        event(s, '%s因王子弃掉%s。' % (NAMES[q], LABEL[dropped['name']]))
        invalidate(s, q)
        if dropped['name'] == 'Princess': eliminate(s, q)
        else:
            source = g['deck'] if g['deck'] else g['reserve']
            g['hands'][q].append(source.pop(0))
    elif name == 'King':
        g['hands'][p], g['hands'][q] = g['hands'][q], g['hands'][p]
        for x in PLAYERS: invalidate(s, x)
        # Each participant knows the card they just gave away, until a later hand change.
        for viewer, target in ((p,q), (q,p)):
            private(s, viewer, 'hand', target=target, card=g['hands'][target][0]['name'],
                    epoch=g['hand_epoch'][target], current=True, source='King')
    elif name == 'Princess': eliminate(s, p)
    if sum(g['alive'].values()) == 1 or not g['deck']: finish_round(s)
    else:
        s['current_player'] = other(p); begin_turn(s, other(p))

def public(s):
    g = s['game_state']
    # reserve is face_down_removed (HOST_ONLY); removed is face_up_removed (PUBLIC).
    return {'round': g['round'], 'scores': g['scores'], 'goal': g['goal'],
            'deck_count': len(g['deck']), 'removed': [c['name'] for c in g['removed']],
            'face_up_removed': [c['name'] for c in g['removed']], 'face_down_removed_count': len(g['reserve']),
            'discards': {p: [c['name'] for c in g['discards'][p]] for p in PLAYERS},
            'protected': g['protected'], 'alive': g['alive']}

def extra_view(s, p): return {}

def zones(s):
    g = s['game_state']
    return g['deck'] + g['reserve'] + g['removed'] + sum(g['hands'].values(), []) + sum(g['discards'].values(), [])

def expected(s): return Counter(COUNTS)
