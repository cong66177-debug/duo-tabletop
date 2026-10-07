"""Original Edition copyright 2017: five starting cards, non-stacking Attack."""
from collections import Counter
from itertools import combinations
from .common import *

VERSION = 'exploding-kittens-original-2017-special-combos-2p-v1'
CATS = ('Taco Cat', 'Cattermelon', 'Hairy Potato Cat', 'Beard Cat', 'Rainbow-Ralphing Cat')
COUNTS = {'Exploding Kitten': 4, 'Defuse': 6, 'Attack': 4, 'Skip': 4, 'Favor': 4,
          'Shuffle': 4, 'See the Future': 5, 'Nope': 5, **{n: 4 for n in CATS}}
LABEL = {'Exploding Kitten': '爆炸猫', 'Defuse': '拆弹', 'Attack': '攻击', 'Skip': '跳过',
         'Favor': '索要', 'Shuffle': '洗牌', 'See the Future': '预知未来', 'Nope': '否决', **{n: n for n in CATS}}
FUNCTIONS = ('Attack', 'Skip', 'Favor', 'Shuffle', 'See the Future')
LABEL.update({'Taco Cat':'塔可猫', 'Cattermelon':'西瓜猫', 'Hairy Potato Cat':'毛茸茸猫',
              'Beard Cat':'胡子猫', 'Rainbow-Ralphing Cat':'彩虹猫'})
EMOJI = {'Defuse':'🧯','Attack':'⚔️','Shuffle':'🔀','Skip':'⏭️','Favor':'🤲',
         'See the Future':'🔮','Nope':'🚫','Exploding Kitten':'💣', **{n:'🐱' for n in CATS}}
EFFECT = {'Defuse':'抽到炸弹时自动拆弹，再秘密插回。', 'Attack':'结束自己全部待执行回合，对方执行两个完整回合；2017版不叠加。',
          'Shuffle':'随机重洗牌堆，双方旧牌序知识失效；不结束回合。', 'Skip':'免抽牌，结束一个待执行回合。',
          'Favor':'对方选择交给你一张牌；不结束回合。', 'See the Future':'私下查看顶部最多3张；不结束回合。',
          'Nope':'响应中取消行动；可再次否决，奇数取消、偶数恢复。', 'Exploding Kitten':'抽到时必须拆弹，否则出局。',
          **{n:'单张无效果；同名两张随机偷1张，三张索要指定牌，五种不同取回弃牌。' for n in CATS}}

def introduce(s):
    for p in PLAYERS:
        seen = s['public_state'].setdefault('introduced', {}).setdefault(p, [])
        for n,count in Counter(c['name'] for c in s['game_state']['hands'][p]).items():
            if n in seen: continue
            seen.append(n)
            event(s,'%s%s ×%d：%s' % (EMOJI[n],LABEL[n],count,EFFECT[n]),
                  visibility='PLAYER_ONLY' if p == 'human' else 'NULL_ONLY', kind='card_intro')

def setup(s):
    all_cards = cards_from_counts(COUNTS, 'ek')
    defuses = [c for c in all_cards if c['name'] == 'Defuse']
    bombs = [c for c in all_cards if c['name'] == 'Exploding Kitten']
    deck = [c for c in all_cards if c['name'] not in ('Defuse', 'Exploding Kitten')]
    rng = Randomness(s['randomness_state']); rng.shuffle(deck)
    hands = {p: [defuses.pop()] + [deck.pop(0) for _ in range(4)] for p in PLAYERS}
    deck.extend(defuses[:2]); deck.append(bombs[0]); rng.shuffle(deck)
    s['game_state'] = {'deck': deck, 'hands': hands, 'discards': [],
                       'removed': defuses[2:] + bombs[1:], 'pending_bomb': [],
                       'deck_epoch': 0, 'alive': {p: True for p in PLAYERS}}
    s['turn_state'] = {'phase': 'play', 'turns_remaining': 1}
    event(s, '爆炸猫开始：2017经典版，双方各5张（含拆弹），三个Special Combos启用，Attack不叠加。')

def clear_future(s):
    s['game_state']['deck_epoch'] += 1
    for p in PLAYERS:
        for k in s['private_knowledge'][p]:
            if k['kind'] in ('future', 'bomb_position'): k['current'] = False

def shifted(s):
    # Public draw permits the owner to track already-seen positions, not to learn new cards.
    for p in PLAYERS:
        for k in s['private_knowledge'][p]:
            if not k.get('current'): continue
            if k['kind'] == 'future':
                k['cards'] = k['cards'][1:]
                if not k['cards']: k['current'] = False
            elif k['kind'] == 'bomb_position':
                k['position'] -= 1
                if k['position'] < 0: k['current'] = False

def finish_turn(s):
    t = s['turn_state']; remaining = t['turns_remaining'] - 1
    if remaining:
        t.update(phase='play', turns_remaining=remaining)
    else:
        s['current_player'] = other(s['current_player'])
        t.update(phase='play', turns_remaining=1)
    event(s, '%s行动，待执行 %d 回合。' % (NAMES[s['current_player']], t['turns_remaining']))

def legal(s, p):
    if s['status'] != 'active': return []
    g = s['game_state']; t = s['turn_state']; h = Counter(c['name'] for c in g['hands'][p])
    phase = t['phase']
    if phase == 'response':
        if t['responder'] != p: return []
        return [{'type': 'pass'}] + ([{'type': 'nope'}] if h['Nope'] else [])
    if phase == 'favor':
        if t['giver'] != p: return []
        return [{'type': 'give', 'card': n} for n in sorted(h)]
    if phase == 'insert':
        if s['current_player'] != p: return []
        return [{'type': 'insert', 'position': i} for i in range(len(g['deck'])+1)]
    if phase != 'play' or s['current_player'] != p: return []
    actions = [{'type': 'draw'}]
    actions.extend({'type': 'play', 'card': n} for n in FUNCTIONS if h[n])
    for n, count in sorted(h.items()):
        if count >= 2: actions.append({'type': 'combo2', 'cards': [n, n]})
        if count >= 3:
            actions.extend({'type': 'combo3', 'cards': [n]*3, 'request': target}
                           for target in COUNTS if target != 'Exploding Kitten')
    # Options depend only on one's own hand and the public discard, never opponent contents.
    for names in combinations(sorted(h), 5):
        targets = sorted(set(names) | {c['name'] for c in g['discards']})
        actions.extend({'type': 'combo5', 'cards': list(names), 'retrieve': n} for n in targets)
    return actions

def transfer(s, giver, taker, name):
    g = s['game_state']; g['hands'][taker].append(take(g['hands'][giver], name))
    private(s, giver, 'transfer', card=name, direction='out', current=False)
    private(s, taker, 'transfer', card=name, direction='in', current=False)
    # Card identity is known only to the participants. Fixed public narration omits it.
    event(s, '%s给了%s一张牌。' % (NAMES[giver], NAMES[taker]), kind='transfer', giver=giver, taker=taker)
    for p in PLAYERS:
        event(s, '转移牌：%s。' % LABEL[name], visibility='PLAYER_ONLY' if p == 'human' else 'NULL_ONLY',
              kind='transfer_identity', card=name, giver=giver, taker=taker)

def resolve(s):
    t = s['turn_state']; pending = t.pop('pending'); nopes = t.pop('nopes')
    t.pop('responder'); t.pop('passes')
    t['phase'] = 'play'
    if nopes % 2:
        event(s, '行动被否决，已出的牌留在弃牌堆。'); return
    g = s['game_state']; p = pending['actor']; q = other(p); a = pending['action']; typ = a['type']
    if typ == 'combo2':
        if g['hands'][q]:
            i = Randomness(s['randomness_state']).below(len(g['hands'][q]), 'random-steal')
            transfer(s, q, p, g['hands'][q][i]['name'])
        else: event(s, '对方没有手牌，偷牌无效。')
    elif typ == 'combo3':
        event(s, '%s索要%s。' % (NAMES[p], LABEL[a['request']]))
        if any(c['name'] == a['request'] for c in g['hands'][q]): transfer(s, q, p, a['request'])
        else: event(s, '对方没有这张牌，索要失败。')
    elif typ == 'combo5':
        g['hands'][p].append(take(g['discards'], a['retrieve']))
        event(s, '%s从弃牌堆取回%s。' % (NAMES[p], LABEL[a['retrieve']]))
    else:
        name = a['card']
        if name == 'Attack':
            s['current_player'] = q; t['turns_remaining'] = 2
            event(s, '%s需要执行两个完整回合（本版本Attack不叠加）。' % NAMES[q])
        elif name == 'Skip': finish_turn(s)
        elif name == 'Favor':
            if g['hands'][q]: t.update(phase='favor', giver=q, taker=p)
            else: event(s, '对方没有手牌，索要无效。')
        elif name == 'Shuffle':
            Randomness(s['randomness_state']).shuffle(g['deck']); clear_future(s)
            event(s, '牌堆已重新洗牌，旧牌序知识失效。')
        elif name == 'See the Future':
            private(s, p, 'future', cards=[c['name'] for c in g['deck'][:3]],
                    epoch=g['deck_epoch'], current=True)
            event(s, '%s私下查看了顶部最多3张牌。' % NAMES[p])

def act(s, p, a):
    # Canonicalize unordered combo selections, so natural-language card order is irrelevant.
    if a.get('type') == 'combo5': a = dict(a, cards=sorted(a.get('cards', [])))
    require(a in legal(s, p), '行动不合法：检查手牌、组合数量、响应窗口、插回位置或当前回合。')
    g = s['game_state']; t = s['turn_state']; typ = a['type']
    if typ == 'pass':
        t['passes'] += 1
        if t['passes'] == 2: resolve(s)
        else: t['responder'] = other(p)
    elif typ == 'nope':
        g['discards'].append(take(g['hands'][p], 'Nope'))
        t['nopes'] += 1; t['passes'] = 0; t['responder'] = other(p)
        event(s, '%s打出了否决（第%d次）。' % (NAMES[p], t['nopes']))
    elif typ == 'give':
        transfer(s, p, t['taker'], a['card'])
        t.pop('giver'); t.pop('taker'); t['phase'] = 'play'
    elif typ == 'insert':
        position = a['position']; clear_future(s)
        g['deck'].insert(position, g['pending_bomb'].pop())
        private(s, p, 'bomb_position', position=position, current=True)
        event(s, '%s秘密插回了爆炸猫。' % NAMES[p]); finish_turn(s)
    elif typ == 'draw':
        require(g['deck'], '牌堆为空：存档异常。')
        c = g['deck'].pop(0); shifted(s)
        if c['name'] == 'Exploding Kitten':
            event(s, '%s抽到了爆炸猫。' % NAMES[p])
            if any(x['name'] == 'Defuse' for x in g['hands'][p]):
                g['discards'].append(take(g['hands'][p], 'Defuse')); g['pending_bomb'].append(c)
                t['phase'] = 'insert'; event(s, '%s使用了拆弹，现在秘密选择插回位置。' % NAMES[p])
            else:
                g['discards'].append(c); g['discards'].extend(g['hands'][p]); g['hands'][p] = []
                g['alive'][p] = False; s['status'] = 'finished'; g['winners'] = [other(p)]
                event(s, '%s爆炸出局，%s获胜。' % (NAMES[p], NAMES[other(p)]))
        else:
            g['hands'][p].append(c)
            private(s, p, 'draw', card=c['name'], current=False)
            event(s, '%s摸了1张牌，没有爆炸。' % NAMES[p], kind='safe_draw', actor=p); finish_turn(s)
    else:
        names = [a['card']] if typ == 'play' else a['cards']
        for name in names: g['discards'].append(take(g['hands'][p], name))
        event(s, '%s打出了%s%s。' % (NAMES[p], '、'.join(LABEL[n] for n in names),
                                     '' if typ == 'play' else '（组合，忽略原牌效）'), kind='play', actor=p, cards=names, action_type=typ)
        t.update(phase='response', pending={'actor': p, 'action': a},
                 responder=other(p), nopes=0, passes=0)

def public(s):
    g = s['game_state']; t = s['turn_state']
    result = {'deck_count': len(g['deck']), 'discards': [c['name'] for c in g['discards']],
              'alive': g['alive'], 'turns_remaining': t['turns_remaining']}
    if t['phase'] == 'response':
        result['response'] = {'actor': t['pending']['actor'], 'action': t['pending']['action'],
                              'nopes': t['nopes'], 'responder': t['responder'], 'passes': t['passes']}
    if t['phase'] == 'favor': result['favor'] = {'giver': t['giver'], 'taker': t['taker']}
    return result

def extra_view(s, p): return {}

def zones(s):
    g = s['game_state']
    return g['deck'] + sum(g['hands'].values(), []) + g['discards'] + g['removed'] + g['pending_bomb']

def expected(s): return Counter(COUNTS)
