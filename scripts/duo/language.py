"""Conservative Chinese/English intent parser. Ambiguity produces no mutation."""
import re
from . import love_letter as ll, kittens as ek
from .common import RuleError, other

GAME_ALIASES = {'love_letter': ('love letter','loveletter','情书','情書'),
                'exploding_kittens': ('exploding kittens','爆炸猫','爆炸貓','炸弹猫','炸彈貓'),
                'incan_gold': ('incan gold','diamant','印加宝藏','印加寶藏','探险','探險')}
ALIASES = {
    'Guard': ('卫兵','衛兵','守卫','侍卫','警卫','guard'),
    'Priest': ('牧师','祭司','神父','priest'), 'Baron': ('男爵','baron'),
    'Handmaid': ('侍女','女仆','handmaid'), 'Prince': ('王子','prince'),
    'King': ('国王','國王','king'), 'Countess': ('伯爵夫人','女伯爵','countess'),
    'Princess': ('公主','princess'),
    'Defuse': ('拆弹','拆彈','解爆','defuse'), 'Attack': ('攻击','攻擊','attack'),
    'Skip': ('跳过','跳過','skip'), 'Favor': ('索要','恩惠','人情','favor','favour'),
    'Shuffle': ('洗牌','shuffle'), 'See the Future': ('预知未来','預知未來','看未来','看未來','see the future'),
    'Nope': ('否决','否決','不行','nope'),
    'Taco Cat': ('taco cat','tacocat','塔可猫'), 'Cattermelon': ('cattermelon','西瓜猫'),
    'Hairy Potato Cat': ('hairy potato cat','potato cat','土豆猫','马铃薯猫','毛茸茸猫'),
    'Beard Cat': ('beard cat','胡子猫'),
    'Rainbow-Ralphing Cat': ('rainbow-ralphing cat','rainbow ralphing cat','彩虹猫')}

def normalize(text): return re.sub(r'\s+', ' ', text.strip().lower()).strip('。！!？? ')

def game_intent(text):
    t = normalize(text)
    if re.search(r'如果|假如|假设|举例|例如|if |suppose ',t): return None
    if re.search(r'不|别|没|don.t|not ',t): return None
    if not (any(x in t for x in ('开始','来一','玩一','新游戏','结束','start','new game'))
            or t in ('我们去探险','我们去探險','去探险','去探險','一起去探险')): return None
    return next((game for game, names in GAME_ALIASES.items() if any(n in t for n in names)), None)

def mentions(text, names):
    matches = []
    for name in names:
        for alias in ALIASES.get(name, (name.lower(),)):
            m = re.search(r'(?<![a-z])'+re.escape(alias)+r'(?![a-z])', text) if alias.isascii() else re.search(re.escape(alias),text)
            if m:
                matches.append((m.start(), name)); break
    return [n for _,n in sorted(matches)]

def single(text, names, message='请说清楚牌名。'):
    found = mentions(text, names)
    if len(found) != 1: raise RuleError(message)
    return found[0]

def parse(s, text):
    t = normalize(text); game = s['game_type']; phase = s['turn_state']['phase']
    if re.search(r'如果|假如|假设|举例|例如|会怎样|会怎么样|if |suppose ',t):
        raise RuleError('这是规则咨询或假设语句，未提交动作。实际行动请直接说要做什么。')
    if t in ('下一轮','下轮','继续下一轮','next round'): return {'type':'next_round'}
    if game == 'incan_gold':
        if re.search(r'不想|不要|不回|不返|不继|不撤|别|don.t|not ',t):
            raise RuleError('这句话带有否定，暂不提交选择。请直接说“继续深入”或“返回营地”。')
        retreat = any(x in t for x in ('回营','返回','撤退','跑路','回去','怂','return','retreat'))
        advance = any(x in t for x in ('继续','深入','往里面走','往里走','留下','留在','continue'))
        if retreat and advance: raise RuleError('继续和返回是两种不同选择，请选一个。')
        if retreat: return {'type':'return'}
        if advance: return {'type':'continue'}
        raise RuleError('请选择“继续深入”或“返回营地”。')
    if game == 'love_letter':
        target = 'human' if any(x in t for x in ('自己','我自己','对我','给我','self')) else 'ai'
        if '猜' in t or 'guess' in t:
            if re.search(r'不是|不想|不要|不猜|don.t|not ',t): raise RuleError('猜牌语句带有否定，未提交动作。请明确要猜的牌名。')
            part = re.split('猜|guess', t, maxsplit=1)[1]
            guess = single(part, ll.COUNTS, '卫兵要猜一个非卫兵牌名，例如“猜你是王子”。')
            action = {'type':'play','card':'Guard','target':'ai','guess':guess}
        else:
            if re.search(r'不想|不要|不出|不打|别|don.t|not ',t): raise RuleError('检测到否定，未提交动作。请明确要打出的牌。')
            name = single(t, ll.COUNTS)
            action = {'type':'play','card':name}
            if name == 'Guard': raise RuleError('要猜什么牌？例如“猜你是男爵”。卫兵不能猜卫兵。')
            if name in ('Priest','Baron','King','Prince'): action['target'] = target
        name = action['card']
        if name in ('Guard','Priest','Baron','King') and s['game_state']['protected']['ai']:
            action = {'type':'play','card':name,'target':None}
        # Default Prince targets opponent, unless the only legal target is oneself.
        if name == 'Prince' and target == 'ai' and s['game_state']['protected']['ai']:
            action['target'] = 'human'
        return action
    if game == 'exploding_kittens':
        if phase == 'response':
            if t in ('过','不否决','不否決','不响应','不响应了','让它生效','继续','pass','通过','我不出否决','我不出nope'): return {'type':'pass'}
            if re.fullmatch(r'(我)?(不想|不要|不)(出|打|使用)?(否决|否決|nope)',t): return {'type':'pass'}
            if re.search(r'不想|不要|不出|不打|不否|别|don.t|not |张',t): raise RuleError('否决窗口只能选择出一张否决或“过”，请明确选择。')
            if single_nope(t): return {'type':'nope'}
            raise RuleError('现在是否决窗口，请说“否决”或“过”；两人都过后牌效才执行。')
        # Deny negation before every mutating EK branch. Only explicit no-play draw
        # wording is exempt; a remaining '不抽' still makes the whole message ambiguous.
        checked = t
        if phase == 'play':
            checked = checked.replace('什么都不出','').replace('不出牌','')
        if re.search(r'不|别|没|don.t|not ',checked):
            raise RuleError('这句话带有否定，未提交动作。请明确要出的牌、抽牌、交牌或插回位置。')
        if phase == 'insert':
            n = len(s['game_state']['deck'])
            if any(x in t for x in ('顶部','最上','顶上','top')): pos = 0
            elif any(x in t for x in ('底部','最下','bottom')): pos = n
            elif '随机' in t or 'random' in t: return {'type':'insert_random'}
            else:
                m = re.search(r'(-?\d+)',t)
                if not m: raise RuleError('选择顶部、底部、随机，或“放在第N张”（顶部第1张，底部第%d张）。' % (n+1))
                pos = int(m.group())-1
            return {'type':'insert','position':pos}
        if phase == 'favor': return {'type':'give','card':single(t,ek.COUNTS)}
        if any(x in t for x in ('直接抽','抽牌','抽一张','什么都不出','不出牌','draw')) or t == '抽': return {'type':'draw'}
        if re.search(r'(五|5)\s*张|five|combo5',t):
            parts = re.split(r'取回|拿回|捡回|回收|换回|retrieve',t,maxsplit=1)
            if len(parts) != 2: raise RuleError('五张组合请列出五个不同牌名，并说“取回某牌”。')
            return {'type':'combo5','cards':sorted(mentions(parts[0],ek.COUNTS)), 'retrieve':single(parts[1],ek.COUNTS)}
        match = re.search(r'(两|二|2|三|3)\s*张|two of a kind|three of a kind|combo[23]',t)
        if match:
            number = 3 if any(x in match.group() for x in ('三','3','three')) else 2
            # Identify the played card before the theft/request phrase, then parse request separately.
            parts = re.split(r'索要|偷|我要|要你|换|steal|request',t,maxsplit=1)
            name = single(parts[0],ek.COUNTS,'组合需要明确同名牌，例如“两张攻击偷你的牌”。')
            a = {'type':'combo%d'%number,'cards':[name]*number}
            if number == 3:
                if len(parts) != 2: raise RuleError('三张组合还需要索要的牌名，例如“三张Taco Cat索要拆弹”。')
                a['request'] = single(parts[1],ek.COUNTS,'请明确索要哪种牌。')
            return a
        if re.search(r'不想|不要|不出|不打|别|don.t|not ',t): raise RuleError('检测到否定，未提交动作。请明确要出的牌或说“直接抽牌”。')
        return {'type':'play','card':single(t,ek.COUNTS)}
    raise RuleError('未知游戏。')

def single_nope(t): return bool(mentions(t, ('Nope',)))
