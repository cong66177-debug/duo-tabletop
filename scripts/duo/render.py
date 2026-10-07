"""Human-only chat display. Public narration cannot serialize AI private objects."""
from collections import Counter
from . import love_letter as ll, kittens as ek, incan
from .visibility import audit_view
from .common import StateError
from .personality import line as banter

TITLES = {'love_letter':'情书','exploding_kittens':'爆炸猫','incan_gold':'印加宝藏'}

def render(v, new_events=None):
    audit_view(v,'human')
    records = v['event_records'][-8:] if new_events is None else new_events
    if any(e not in v['event_records'] for e in records):
        raise StateError('展示事件不属于已核准的玩家视图。')
    lines = []
    if v['mode'] == 'debug': lines.append('【DEBUG测试局，不是正式游戏】')
    edition = {'love_letter':'经典16张', 'exploding_kittens':'2017经典版',
               'incan_gold':'编号遗物随机加入' if v['ruleset_version']==incan.VERSION else '编号遗物按轮加入'}
    lines.append('%s｜%s' % (TITLES[v['game_type']],edition[v['game_type']]))
    if v['mode']=='debug': lines.append('会话 %s｜修订 %d' % (v['session_id'],v['revision']))
    lines.extend(e['text'] for e in records)
    game = v['game_type']; p = v['public']
    if 'your_hand' in v:
        label = ll.LABEL if game == 'love_letter' else ek.LABEL
        counts = Counter(v['your_hand'])
        lines.append('\n你的手牌（%d张）' % sum(counts.values()))
        for name,n in counts.items(): lines.append('%s%s ×%d' % (ek.EMOJI[name] if game == 'exploding_kittens' else '',label[name],n))
        lines.append('Null手牌：%d张\n牌堆：%d张' % (v['opponent_hand_count'],p['deck_count']))
        if game == 'love_letter':
            lines.append('公开移除：'+'、'.join(label[n] for n in p['removed']))
            lines.append('好感：你 %d / Null %d（先到7）' % (p['scores']['human'],p['scores']['ai']))
            lines.append('公开弃牌：你 [%s]；Null [%s]' % ('、'.join(label[n] for n in p['discards']['human']), '、'.join(label[n] for n in p['discards']['ai'])))
            if p['protected']['human']: lines.append('你受到侍女保护。')
            if p['protected']['ai']: lines.append('Null受到侍女保护。')
        else:
            lines.append('弃牌堆：' + ('、'.join('%s ×%d'%(label[n],c) for n,c in Counter(p['discards']).items()) or '空'))
            lines.append('当前玩家：%s；待执行回合：%d' % ('你' if v['current_player']=='human' else 'Null',p['turns_remaining']))
            for e in records:
                if e.get('kind') == 'play':
                    for name in dict.fromkeys(e['cards']):
                        effect = ek.EFFECT[name] if e['action_type'] == 'play' else '本次是组合材料，忽略原牌效；组合不结束回合。'
                        lines.append('%s%s（打出%d张；你现持%d张）：%s' % (ek.EMOJI[name],label[name],e['cards'].count(name),counts[name],effect))
        for k in v['private_knowledge']:
            if k['kind'] == 'hand' and not k.get('current'):
                lines.append('你的历史私下观察（%s）：Null当时持有%s；其后摸牌/换牌，已不能确定当前手牌。' % (k.get('source','查看'),label[k['card']]))
            if not k.get('current'): continue
            if k['kind'] == 'hand': lines.append('你私下知道：Null目前持有%s。' % label[k['card']])
            if k['kind'] == 'future': lines.append('你私下看到的当前顶部牌序：'+' → '.join(label[n] for n in k['cards']))
            if k['kind'] == 'bomb_position': lines.append('你知道：爆炸猫当前在第%d张。' % (k['position']+1))
    else:
        lines.append('\n第%d / 5轮｜你未带回：%d颗｜Null未带回：%d颗｜路径余宝石：%d颗' % (p['round'],p['loot']['human'],p['loot']['ai'],p['path_gems']))
        lines.append('你已安全带回：%d颗；你的遗物：%s' % (v['your_bank'],'、'.join(str(x) for x in p['artifacts']['human']) or '无'))
        lines.append('Null遗物：%s；帐篷内财富不由程序公开' % ('、'.join(str(x) for x in p['artifacts']['ai']) or '无'))
        lines.append('危险：' + ('、'.join('%s ×%d'%(incan.LABEL[n],c) for n,c in p['hazards'].items()) or '无'))
        lines.append('路径遗物：'+('、'.join(str(c['value']) for c in p['path'] if c['name']=='Artifact') or '无'))
        lines.append('牌堆：%d张' % p['deck_count'])
        if v.get('ai_commitment_sha256'):
            lines.append('Null已秘密锁定选择，承诺SHA256：'+v['ai_commitment_sha256'])
        if v.get('last_reveal'):
            r = v['last_reveal']
            lines.append('上次揭晓证明：第%d轮/决策%d，选择=%s，nonce=%s' % (r['round'],r['decision_number'],r['choice'],r['nonce']))
    if v['status'] != 'active':
        lines.append('\n本局已结束。想重开请说“开始新游戏”。'); return '\n'.join(lines)
    phase = v['phase']
    if phase == 'round_end': lines.append('\n说“下一轮”继续这场游戏。')
    elif game == 'love_letter': lines.append('\n请出一张牌；卫兵请同时说猜的牌名。')
    elif phase == 'response':
        r = p['response']; a = r['action']
        desc = ek.LABEL[a['card']] if a['type']=='play' else {'combo2':'对子偷牌','combo3':'三张索要','combo5':'五张取回'}[a['type']]
        lines.append('\n等待你响应：%s的%s尚未结算；否决次数%d（%s）。说“否决”或“过”。' %
                     ('Null' if r['actor']=='ai' else '你',desc,r['nopes'],'当前取消' if r['nopes']%2 else '当前生效'))
    elif phase == 'favor': lines.append('\n请选择交给Null的一张手牌。')
    elif phase == 'insert': lines.append('\n秘密插回：顶部 / 底部 / 随机 / 第N张（1至%d）。' % (p['deck_count']+1))
    elif game == 'exploding_kittens':
        lines.append('\n你的行动阶段：可以继续出牌或组合，或“直接抽牌”结束一个回合。' if v['current_player']=='human' else '\nNull正在执行自己的回合。')
    elif phase == 'decision': lines.append('\n你选择：继续深入 / 返回营地。双方选择锁定后同时揭晓。')
    speech = banter(v,records)
    if speech: lines.append(speech)
    return '\n'.join(lines)
