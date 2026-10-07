"""Host-side invariants and turn transition checks. No state repair or narration."""
import hashlib
from .common import PLAYERS, StateError
from .visibility import HOST_FIELDS, VISIBILITIES, owner_label

def check(condition, reason):
    if not condition: raise StateError(reason)

def commitment(s, c):
    payload = '%s:%d:%d:%s:%s' % (s['session_id'], s['game_state']['round'],
               s['turn_state']['decision_number'], c['choice'], c['nonce'])
    check(c['choice'] in ('continue','return') and hashlib.sha256(payload.encode()).hexdigest() == c['sha256'],
          '同步选择承诺校验失败。')

def state(s):
    g, t = s['game_state'], s['turn_state']
    if 'deck_count' in g: check(g['deck_count'] == len(g['deck']), '牌堆缓存计数漂移。')
    for p in PLAYERS:
        if p+'_hand_count' in g: check(g[p+'_hand_count'] == len(g['hands'][p]), '手牌缓存计数漂移。')
    check(s['visibility'] == {k:'HOST_ONLY' for k in HOST_FIELDS}, '主持人信息分区损坏。')
    check(set(s['private_knowledge']) == set(PLAYERS), '私人知识分区损坏。')
    for e in s['public_state']['events']:
        check(isinstance(e,dict) and e.get('visibility') in VISIBILITIES and isinstance(e.get('text'),str), '事件缺少信息权限。')
    for p in PLAYERS:
        check(all(k.get('visibility') == owner_label(p) for k in s['private_knowledge'][p]), '私人信息归属错误。')
    check(s['status'] in ('active','finished','abandoned'), '游戏状态错误。')
    if s['game_type'] == 'love_letter':
        check(t['phase'] in ('play','round_end'), '情书阶段错误。')
        if s['status']=='active' and t['phase']=='play':
            check(s['current_player'] in PLAYERS and all(g['alive'].values()), '情书当前玩家或存活状态错误。')
            check(all(len(g['hands'][p]) == (2 if p==s['current_player'] else 1) for p in PLAYERS), '情书摸牌/出牌阶段与手牌数不符。')
        for p in PLAYERS:
            check(len(g['hands'][p]) <= 2, '情书手牌超过2张。')
            for k in s['private_knowledge'][p]:
                if k['kind'] == 'hand' and k.get('current'):
                    target = k['target']
                    check(k['epoch'] == g['hand_epoch'][target] and len(g['hands'][target]) == 1
                          and k['card'] == g['hands'][target][0]['name'], '情书私人知识未正确更新。')
    elif s['game_type'] == 'exploding_kittens':
        check(s['current_player'] in PLAYERS and t['phase'] in ('play','response','favor','insert'), '爆炸猫当前玩家或阶段错误。')
        check(type(t['turns_remaining']) is int and t['turns_remaining'] in (1,2), '2017版待执行回合数错误。')
        phase = t['phase']
        check(bool(g['pending_bomb']) == (phase == 'insert') and len(g['pending_bomb']) <= 1, '待插回炸弹与阶段不符。')
        check(all(c['name']=='Exploding Kitten' for c in g['pending_bomb']), '暂存区包含非炸弹牌。')
        if phase == 'response':
            check(t['pending']['actor'] == s['current_player'] and t['responder'] in PLAYERS, '响应者或待执行动作错误。')
            check(type(t['nopes']) is int and t['nopes'] >= 0 and t['passes'] in (0,1), '否决链计数错误。')
        else: check(not any(k in t for k in ('pending','responder','passes','nopes')), '存在未结算的响应动作。')
        if phase == 'favor': check(t['taker'] == s['current_player'] and t['giver'] != t['taker'], '交牌阶段角色错误。')
        else: check('giver' not in t and 'taker' not in t, '存在未结算的索要效果。')
        for p in PLAYERS:
            check(not any(c['name'] == 'Exploding Kitten' for c in g['hands'][p]), '炸弹不能进入普通手牌。')
            for k in s['private_knowledge'][p]:
                if not k.get('current'): continue
                if k['kind'] == 'future':
                    check(k['epoch'] == g['deck_epoch'] and k['cards'] == [c['name'] for c in g['deck'][:len(k['cards'])]], '已知牌序未正确移动或失效。')
                if k['kind'] == 'bomb_position':
                    i = k['position']
                    check(type(i) is int and 0 <= i < len(g['deck']) and g['deck'][i]['name'] == 'Exploding Kitten', '已知炸弹位置失效。')
    else:
        check(1 <= g['round'] <= 5 and t['phase'] in ('decision','round_end','finished'), '探险轮数或阶段错误。')
        check(g['path_gems'] >= 0 and all(x >= 0 for x in g['loot'].values()), '宝石数量错误。')
        check(set(g['active']) <= set(PLAYERS) and len(set(g['active'])) == len(g['active']), '探险者状态错误。')
        check(bool(g['active']) == (t['phase'] == 'decision'), '探险结束条件与阶段不符。')
        check(len(g['future_artifacts']) == 5-g['round'], '待加入遗物数量与轮数不符。')
        if t['phase']=='decision':
            from collections import Counter
            actual = Counter(c['name'] for c in g['path'] if c['name'] in ('Spiders','Mummies','Fire','Snakes','Rockfall'))
            check(dict(actual)==g['hazards'] and all(n==1 for n in actual.values()), '路径危险与探险阶段不符。')
        check(all(g['loot'][p] == 0 for p in PLAYERS if p not in g['active']), '已撤退玩家仍有临时财富。')
        c = t.get('commitment')
        if c:
            check(t['phase'] == 'decision' and 'ai' in g['active'], '同步承诺阶段错误。')
            commitment(s,c)

def transition(before, after, action):
    if before['game_type'] != 'exploding_kittens': return
    t = before['turn_state']; effective = action
    if t['phase'] == 'response':
        if action['type'] != 'pass' or t['passes'] != 1: effective = None
        elif t['nopes'] % 2: effective = None
        else: effective = t['pending']['action']
    if effective and (effective['type'].startswith('combo') or
                     effective.get('card') in ('Favor','Shuffle','See the Future')):
        check(before['current_player'] == after['current_player'] and
              t['turns_remaining'] == after['turn_state']['turns_remaining'], '普通出牌或组合错误结束回合。')
    if effective is None:
        check(before['current_player'] == after['current_player'] and
              t['turns_remaining'] == after['turn_state']['turns_remaining'], '否决响应错误结束回合。')

def output(s, view):
    if s['status'] != 'active': return
    check(bool(view['legal_actions']), '输出时尚未完成自动行动或仍有未结算阶段。')
    if s['game_type'] == 'incan_gold' and s['turn_state']['phase'] == 'decision' and 'ai' in s['game_state']['active']:
        check(s['turn_state']['commitment'] is not None, '输出前Null同步选择尚未锁定。')
