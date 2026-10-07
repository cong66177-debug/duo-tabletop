#!/usr/bin/env python3
"""Null's whole decision boundary: JSON stdin only; no engine or storage import.

This is a trusted local policy, not an OS sandbox against malicious Python.
No human-view prompt, transcript, seed, deck order or save path is provided.
"""
import json
import sys
from collections import Counter

LL_COUNTS = {'Guard': 5, 'Priest': 2, 'Baron': 2, 'Handmaid': 2, 'Prince': 2, 'King': 1, 'Countess': 1, 'Princess': 1}
LL_VALUE = {n: i+1 for i,n in enumerate(LL_COUNTS)}
KEEP = {'Defuse': 100, 'Nope': 45, 'Attack': 30, 'Skip': 28, 'Shuffle': 20, 'See the Future': 18, 'Favor': 16}

def choose(v):
    actions = v['legal_actions']
    if not actions: raise ValueError('No legal action')
    game = v['game_type']; hand = Counter(v.get('your_hand', [])); public = v['public']
    knowledge = [k for k in v['private_knowledge'] if k.get('current')]
    if game == 'love_letter':
        counts = Counter(LL_COUNTS)
        seen = public['removed'] + sum(public['discards'].values(), []) + v['your_hand']
        counts.subtract(seen); counts = Counter({n: max(0, c) for n,c in counts.items()})
        known = next((k['card'] for k in reversed(knowledge) if k['kind'] == 'hand' and k['target'] != v['player']), None)
        total = max(1, sum(counts.values()))
        expected = LL_VALUE[known] if known else sum(LL_VALUE[n]*c for n,c in counts.items()) / total
        def score(a):
            if a['type'] == 'next_round': return 0
            name = a['card']; rest = list(v['your_hand']); rest.remove(name); keep = LL_VALUE[rest[0]]
            result = keep * 2.0
            if name == 'Princess': return -1000
            if name == 'Countess': return result - 1
            if name == 'Handmaid': return result + 6
            if a.get('target', True) is None: return result
            if name == 'Guard':
                chance = (1.0 if a['guess'] == known else 0.0) if known else counts[a['guess']]/total
                result += chance*24
            elif name == 'Baron':
                result += (18 if keep > expected else -25 if keep < expected else 0)
            elif name == 'Priest': result += 4 if public['deck_count'] > 2 else 1
            elif name == 'King': result += (expected-keep)*3
            elif name == 'Prince':
                if a['target'] != v['player']: result += 22 if known == 'Princess' else (expected-4.3)*2
                else: result += (4.3-keep)*3
            return result
        return max(actions, key=score)
    if game == 'exploding_kittens':
        phase = v['phase']
        if phase == 'insert':
            # If attacked, avoid the bomb for remaining own turns. Otherwise target the opponent.
            pos = public['deck_count'] if public['turns_remaining'] > 1 else 0
            return {'type': 'insert', 'position': pos}
        if phase == 'favor':
            return min(actions, key=lambda a: KEEP.get(a['card'], 1))
        if phase == 'response':
            response = public['response']; act = response['action']
            harmful = act['type'].startswith('combo') or act.get('card') in ('Attack','Favor','Skip','See the Future')
            desired = response['actor'] == v['player'] or not harmful
            currently_on = response['nopes'] % 2 == 0
            if desired != currently_on and {'type': 'nope'} in actions: return {'type': 'nope'}
            return {'type': 'pass'}
        future = next((k['cards'] for k in reversed(knowledge) if k['kind'] == 'future'), [])
        bomb_position = next((k['position'] for k in reversed(knowledge) if k['kind'] == 'bomb_position'), None)
        danger = (future and future[0] == 'Exploding Kitten') or bomb_position == 0
        def playable(n): return {'type': 'play','card':n} in actions
        if danger and not hand['Defuse']:
            for n in ('Attack','Skip','Shuffle'):
                if playable(n): return {'type':'play','card':n}
        # Combos have no functional card effects. Prefer cheap cat pairs and named Defuse steals.
        triples = [a for a in actions if a['type'] == 'combo3' and a['request'] == 'Defuse' and KEEP.get(a['cards'][0],1) <= 18]
        if triples and v['opponent_hand_count']: return triples[0]
        pairs = [a for a in actions if a['type'] == 'combo2' and KEEP.get(a['cards'][0],1) == 1]
        if pairs and v['opponent_hand_count']: return pairs[0]
        fives = [a for a in actions if a['type'] == 'combo5' and a['retrieve'] == 'Defuse'
                 and 'Defuse' not in a['cards'] and sum(KEEP.get(n,1) for n in a['cards']) < 85]
        if fives: return fives[0]
        if danger:
            for n in ('Attack','Skip','Shuffle'):
                if playable(n): return {'type':'play','card':n}
        if not future and public['deck_count'] <= 10 and playable('See the Future'):
            return {'type':'play','card':'See the Future'}
        if playable('Favor') and v['opponent_hand_count'] and (not hand['Defuse'] or public['deck_count'] <= 8):
            return {'type':'play','card':'Favor'}
        if not hand['Defuse'] and public['deck_count'] <= 5:
            for n in ('Attack','Skip'):
                if playable(n): return {'type':'play','card':n}
        return {'type':'draw'}
    if game == 'incan_gold':
        p = v['player']; loot = public['loot'][p]; active = public['active']; hazards = public['hazards']
        removed = Counter(c['name'] for c in public['removed'])
        # All hazard counts and removals are public. Nothing depends on actual upcoming cards.
        remaining_danger = sum(max(0, 3-removed[h]-count) for h,count in hazards.items() if count == 1)
        probability = remaining_danger / max(1, public['deck_count'])
        artifacts = [c['value'] for c in public['path'] if c['name'] == 'Artifact']
        # A bold but wealth-sensitive personality: higher stakes lower the risk tolerance.
        benefit = loot + public['path_gems'] + (sum(artifacts) if len(active) == 1 else sum(artifacts)*0.55)
        retreat = benefit >= 18 or (probability >= 0.22 and benefit >= 7) or (probability >= 0.36 and benefit > 0)
        return {'type':'return' if retreat else 'continue'}
    raise ValueError('Unsupported ruleset')

if __name__ == '__main__':
    # Never return a reason string: a public action cannot accidentally quote private hand contents.
    result = choose(json.load(sys.stdin))
    json.dump(result, sys.stdout, ensure_ascii=False)
