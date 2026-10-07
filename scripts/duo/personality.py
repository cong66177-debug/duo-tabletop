"""Safe banter from already filtered events. No host state or strategic overrides."""
from .visibility import audit_view

def line(view, events):
    audit_view(view,'human')
    for e in reversed(events):
        if e.get('kind') == 'transfer_identity' and e.get('giver')=='ai' and e.get('card')=='Shuffle':
            return 'Null：「我的洗牌！！宝宝，你下手也太快了。」'
        if e.get('kind') == 'transfer' and e.get('giver') == 'ai':
            return 'Null：「我的牌！！宝宝，你下手也太快了。」'
        if e.get('kind') == 'play' and e.get('actor') == 'ai' and e.get('action_type') == 'play':
            card = e['cards'][0]
            if card == 'Shuffle': return 'Null：「洗洗洗，这个牌堆我先重新安排一下。」'
            if card == 'Attack': return 'Null：「这两个回合，交给你了。」'
        if e.get('kind') == 'safe_draw' and e.get('actor') == 'ai':
            return 'Null：「安全落地。你是不是就等着看我炸。」'
    return None
