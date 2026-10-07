"""Information labels, legacy structural migration, and output allowlists."""
import copy
from .common import StateError

VISIBILITIES = {'PUBLIC', 'PLAYER_ONLY', 'NULL_ONLY', 'HOST_ONLY'}
HOST_FIELDS = ('game_state', 'randomness_state', 'turn_state', 'private_knowledge', 'public_state')
VIEW_FIELDS = {'session_id','revision','game_type','ruleset_version','mode','status','player',
    'current_player','phase','public','events','event_records','private_knowledge','legal_actions',
    'your_hand','opponent_hand_count','your_bank','your_score','ai_commitment_sha256',
    'decision_number','last_reveal','reveal_history','visibility'}
PRIVATE_FIELDS = {'your_hand','private_knowledge','legal_actions','your_bank','your_score','events','event_records'}
PUBLIC_FIELDS = {
    'love_letter': {'round','scores','goal','deck_count','removed','face_up_removed','face_down_removed_count','discards','protected','alive'},
    'exploding_kittens': {'deck_count','discards','alive','turns_remaining','response','favor'},
    'incan_gold': {'round','active','loot','path_gems','path','hazards','deck_count','artifacts','removed','scores'}}

def owner_label(player):
    return 'PLAYER_ONLY' if player == 'human' else 'NULL_ONLY'

def visible(record, player):
    return record.get('visibility') in ('PUBLIC', owner_label(player))

def migrate(s):
    """Tag previously trusted v1 engine records; do not alter cards/rules/RNG/decisions."""
    if s.get('schema_version') != 1: return s
    s = copy.deepcopy(s)
    s['schema_version'] = 2
    s['visibility'] = {k:'HOST_ONLY' for k in HOST_FIELDS}
    s['public_state']['events'] = [dict(text=e, kind='narration', visibility='PUBLIC')
                                 if isinstance(e,str) else e for e in s['public_state']['events']]
    for p, knowledge in s['private_knowledge'].items():
        for k in knowledge: k['visibility'] = owner_label(p)
    return s

def records(s, player):
    return [copy.deepcopy(e) for e in s['public_state']['events'] if visible(e,player)]

def label_view(v):
    v['visibility'] = {k:owner_label(v['player']) if k in PRIVATE_FIELDS else 'PUBLIC'
                       for k in v if k != 'visibility'}
    # Nested events carry their own labels even though the filtered container is public.
    return v

def audit_view(v, player=None):
    def check(c):
        if not c: raise StateError('信息权限或展示视图不一致。')
    check(v.get('player') in ('human','ai'))
    check(player is None or v['player'] == player)
    check(set(v) <= VIEW_FIELDS)
    check(set(v['public']) <= PUBLIC_FIELDS[v['game_type']])
    labels = v.get('visibility', {})
    check(set(labels) == set(v)-{'visibility'})
    check(all(labels[k] == (owner_label(v['player']) if k in PRIVATE_FIELDS else 'PUBLIC') for k in labels))
    check(all(visible(e,v['player']) for e in v['event_records']))
    check(v['events'] == [e['text'] for e in v['event_records']])
    check(all(k.get('visibility') == owner_label(v['player']) for k in v['private_knowledge']))
    if 'your_hand' in v:
        check(isinstance(v['your_hand'],list))
        check(v['opponent_hand_count'] >= 0 and v['public']['deck_count'] >= 0)
    if v['game_type'] == 'exploding_kittens' and v['phase'] == 'response':
        check('response' in v['public'])
    return v
