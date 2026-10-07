"""Rules-neutral helpers; private RNG is never part of a player projection."""
import hashlib
import hmac
import secrets
from collections import Counter

PLAYERS = ('human', 'ai')
NAMES = {'human': '你', 'ai': 'Null'}

class RuleError(ValueError):
    pass

class StateError(RuleError):
    """An invariant failure stops the table; never render the suspect state."""
    pass

def require(condition, message):
    if not condition:
        raise RuleError(message)

def other(p):
    return 'ai' if p == 'human' else 'human'

class Randomness:
    """Persisted HMAC counter generator with unbiased rejection sampling."""
    def __init__(self, state):
        self.state = state

    @classmethod
    def new(cls, seed=None):
        return {'algorithm': 'hmac-sha256-counter-v1',
                'key': hashlib.sha256(str(seed).encode()).hexdigest() if seed is not None else secrets.token_hex(32),
                'counter': 0, 'audit': []}

    def below(self, n, reason):
        require(n > 0, '随机范围不能为空。')
        limit = (1 << 256) - ((1 << 256) % n)
        while True:
            c = self.state['counter']
            self.state['counter'] += 1
            b = hmac.new(bytes.fromhex(self.state['key']), str(c).encode(), hashlib.sha256).digest()
            x = int.from_bytes(b, 'big')
            if x < limit:
                r = x % n
                self.state['audit'].append({'counter': c, 'reason': reason, 'n': n, 'result': r})
                return r

    def shuffle(self, cards):
        for i in range(len(cards)-1, 0, -1):
            j = self.below(i+1, 'shuffle')
            cards[i], cards[j] = cards[j], cards[i]

    def choose(self, cards, reason):
        return cards[self.below(len(cards), reason)]

def cards_from_counts(counts, prefix):
    return [{'id': '%s-%s-%s' % (prefix, name, i), 'name': name}
            for name, n in counts.items() for i in range(n)]

def take(hand, name):
    for i, c in enumerate(hand):
        if c['name'] == name:
            return hand.pop(i)
    raise RuleError('你没有这张牌。')

def has_cards(hand, names):
    return not (Counter(names) - Counter(c['name'] for c in hand))

def event(s, text, visibility='PUBLIC', kind='narration', **data):
    from .visibility import VISIBILITIES
    require(visibility in VISIBILITIES, '未知信息权限。')
    s['public_state']['events'].append(dict(text=text, visibility=visibility, kind=kind, **data))

def private(s, p, kind, **data):
    s['private_knowledge'][p].append(dict(kind=kind, visibility='PLAYER_ONLY' if p == 'human' else 'NULL_ONLY', **data))

def fresh_envelope(game, version, debug=False, seed=None):
    import uuid
    return {'schema_version': 2, 'visibility': {'game_state':'HOST_ONLY', 'randomness_state':'HOST_ONLY',
            'turn_state':'HOST_ONLY', 'private_knowledge':'HOST_ONLY', 'public_state':'HOST_ONLY'},
            'session_id': str(uuid.uuid4()), 'game_type': game,
            'game_version': version, 'ruleset_version': version, 'revision': 0,
            'mode': 'debug' if debug else 'play', 'status': 'active',
            'current_player': 'human', 'game_state': {},
            'public_state': {'events': []}, 'private_knowledge': {p: [] for p in PLAYERS},
            'turn_state': {}, 'randomness_state': Randomness.new(seed)}
