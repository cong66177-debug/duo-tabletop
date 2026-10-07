"""Behavioral fixtures, information non-interference, and complete games. Stdlib only."""
import copy
import hashlib
import json
import random
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0,str(SCRIPTS))
from duo import love_letter as ll, kittens as ek, incan as ig
from duo.common import Randomness, RuleError
from duo.engine import create, projection, apply, pump, human_action, validate, ask_ai
from duo.language import parse
from duo.render import render
from duo.store import Store

SEED = '01'*32

def rig_ll(hand, opponent, deck_top=None):
    s = create('love_letter', True, SEED); g = s['game_state']
    pool = ll.zones(s)
    def get(name):
        for i,c in enumerate(pool):
            if c['name'] == name: return pool.pop(i)
        raise AssertionError(name)
    g['hands']={'human':[get(n) for n in hand], 'ai':[get(n) for n in opponent]}
    g['reserve']=[pool.pop()]; g['removed']=[]; g['discards']={'human':[],'ai':[]}
    g['deck']=[get(n) for n in (deck_top or [])]+pool
    return s

def rig_ek(hand, opponent, top=None):
    s=create('exploding_kittens', True, SEED); g=s['game_state']
    # Use only the cards in the legal two-player live game, leaving setup exclusions intact.
    pool = g['deck'] + g['hands']['human'] + g['hands']['ai']
    def get(name):
        for i,c in enumerate(pool):
            if c['name'] == name: return pool.pop(i)
        raise AssertionError(name)
    g['hands']={'human':[get(n) for n in hand], 'ai':[get(n) for n in opponent]}
    selected=[get(n) for n in (top or [])]
    g['deck']=selected+pool; g['discards']=[]
    s['public_state']['events']=[]; s['public_state']['introduced']={p: [c['name'] for c in g['hands'][p]] for p in ('human','ai')}
    return s

def settle(s):
    while s['status']=='active' and s['turn_state']['phase']=='response':
        s=apply(s,s['turn_state']['responder'],{'type':'pass'})
    return s

def rig_ig(names):
    s=create('incan_gold',True,SEED,ruleset=ig.LEGACY_VERSION); g=s['game_state']
    pool=g['deck']+g['path']; g.update(path=[], hazards={}, path_gems=0, loot={'human':0,'ai':0})
    chosen=[]
    for name, value in names:
        for i,c in enumerate(pool):
            if c['name']==name and (value is None or c.get('value')==value): chosen.append(pool.pop(i)); break
        else: raise AssertionError((name,value))
    g['deck']=chosen+pool
    s['turn_state'].update(phase='reveal',decision_number=0,commitment=None)
    ig.reveal(s); return s

class LoveLetterTests(unittest.TestCase):
    def test_two_player_setup_and_conservation(self):
        s=create('love_letter',True,SEED);g=s['game_state']
        self.assertEqual(len(g['reserve']),1);self.assertEqual(len(g['removed']),3)
        self.assertEqual(len(g['hands']['human']),2);self.assertEqual(len(g['hands']['ai']),1)
        self.assertEqual(len(g['deck']),9);validate(s)
    def test_guard_hit_miss_and_cannot_guess_guard(self):
        s=rig_ll(['Guard','Princess'],['Prince'])
        hit=apply(s,'human',{'type':'play','card':'Guard','target':'ai','guess':'Prince'})
        self.assertFalse(hit['game_state']['alive']['ai'])
        miss=apply(s,'human',{'type':'play','card':'Guard','target':'ai','guess':'King'})
        self.assertTrue(miss['game_state']['alive']['ai'])
        before=copy.deepcopy(s)
        with self.assertRaises(RuleError):apply(s,'human',{'type':'play','card':'Guard','target':'ai','guess':'Guard'})
        self.assertEqual(s,before)
    def test_priest_private(self):
        s=rig_ll(['Priest','Princess'],['Prince'])
        # Use a last-card fixture: no next turn draw to invalidate the information.
        g=s['game_state'];g['discards']['human'].extend(g['deck']);g['deck']=[]
        s=apply(s,'human',{'type':'play','card':'Priest','target':'ai'})
        self.assertTrue(any(k.get('card')=='Prince' for k in projection(s,'human')['private_knowledge']))
        self.assertFalse(any(k.get('source')=='Priest' for k in projection(s,'ai')['private_knowledge']))
    def test_priest_expires_after_draw_and_swap(self):
        s=rig_ll(['Priest','Princess'],['Prince'],['Guard'])
        s=apply(s,'human',{'type':'play','card':'Priest','target':'ai'})
        self.assertFalse(s['private_knowledge']['human'][-1]['current'])
        s=rig_ll(['King','Guard'],['Princess'])
        s=apply(s,'human',{'type':'play','card':'King','target':'ai'})
        self.assertEqual(s['game_state']['hands']['human'][0]['name'],'Princess')
        self.assertFalse(s['private_knowledge']['human'][-1]['current'])
    def test_baron_elimination_and_tie(self):
        for mine, theirs, loser in [('Princess','Guard','ai'),('Guard','Princess','human'),('Priest','Priest',None)]:
            s=rig_ll(['Baron',mine],[theirs]);s=apply(s,'human',{'type':'play','card':'Baron','target':'ai'})
            if loser:self.assertFalse(s['game_state']['alive'][loser])
            else:self.assertTrue(all(s['game_state']['alive'].values()))
    def test_handmaid_and_forced_self_prince(self):
        s=rig_ll(['Prince','Guard'],['Princess']);s['game_state']['protected']['ai']=True
        self.assertNotIn({'type':'play','card':'Prince','target':'ai'},ll.legal(s,'human'))
        self.assertIn({'type':'play','card':'Prince','target':'human'},ll.legal(s,'human'))
        s=rig_ll(['Guard','Princess'],['Prince']);s['game_state']['protected']['ai']=True
        s=apply(s,'human',{'type':'play','card':'Guard','target':None})
        self.assertTrue(s['game_state']['alive']['ai']);self.assertFalse(s['game_state']['protected']['ai'])
        s=rig_ll(['Handmaid','Princess'],['Prince']);s=apply(s,'human',{'type':'play','card':'Handmaid'})
        self.assertTrue(s['game_state']['protected']['human'])
    def test_prince_princess_no_replacement(self):
        s=rig_ll(['Prince','Guard'],['Princess']);n=len(s['game_state']['deck'])
        s=apply(s,'human',{'type':'play','card':'Prince','target':'ai'})
        self.assertEqual(len(s['game_state']['deck']),n);self.assertFalse(s['game_state']['alive']['ai'])
    def test_prince_uses_reserved_last_card(self):
        s=rig_ll(['Prince','Guard'],['Priest']);g=s['game_state'];g['discards']['human'].extend(g['deck']);g['deck']=[]
        reserve=g['reserve'][0]['name'];s=apply(s,'human',{'type':'play','card':'Prince','target':'ai'})
        self.assertEqual(s['game_state']['hands']['ai'][0]['name'],reserve);self.assertEqual(s['game_state']['reserve'],[])
        self.assertEqual(s['turn_state']['phase'],'round_end')
    def test_countess_forced_without_hand_leak(self):
        for royal in ('King','Prince'):
            s=rig_ll(['Countess',royal],['Guard'])
            self.assertEqual(ll.legal(s,'human'),[{'type':'play','card':'Countess'}])
            s=apply(s,'human',{'type':'play','card':'Countess'})
            self.assertNotIn('必须',s['public_state']['events'][-1]['text'])
    def test_princess_play_and_hand_discard(self):
        s=rig_ll(['Princess','Guard'],['Priest']);s=apply(s,'human',{'type':'play','card':'Princess'})
        self.assertFalse(s['game_state']['alive']['human']);self.assertEqual(len(s['game_state']['hands']['human']),0)
    def test_deck_end_discard_tiebreak(self):
        s=rig_ll(['Handmaid','Guard'],['Guard']);g=s['game_state'];g['discards']['human'].extend(g['deck']);g['deck']=[]
        s=apply(s,'human',{'type':'play','card':'Handmaid'})
        self.assertEqual(s['game_state']['round_winners'],['human'])

class KittensTests(unittest.TestCase):
    def test_setup_fixed_2017_deck(self):
        s=create('exploding_kittens',True,SEED);g=s['game_state'];validate(s)
        self.assertEqual([len(x) for x in g['hands'].values()],[5,5]);self.assertEqual(len(g['deck']),41)
        self.assertEqual(Counter(c['name'] for c in g['removed']),{'Exploding Kitten':3,'Defuse':2})
    def test_explosion_and_defuse_secret_insert(self):
        s=rig_ek(['Skip'],['Attack'],['Exploding Kitten']);s=apply(s,'human',{'type':'draw'})
        self.assertEqual(s['status'],'finished');self.assertEqual(s['game_state']['winners'],['ai'])
        s=rig_ek(['Defuse'],['Attack'],['Exploding Kitten']);s=apply(s,'human',{'type':'draw'})
        self.assertEqual(s['turn_state']['phase'],'insert')
        s=apply(s,'human',{'type':'insert','position':3})
        self.assertEqual(s['game_state']['deck'][3]['name'],'Exploding Kitten')
        self.assertFalse(any(k['kind']=='bomb_position' for k in projection(s,'ai')['private_knowledge']))
        self.assertNotIn('position',json.dumps(projection(s,'ai')))
        validate(s)
    def test_insert_illegal_no_mutation(self):
        s=rig_ek(['Defuse'],[],['Exploding Kitten']);s=apply(s,'human',{'type':'draw'});before=copy.deepcopy(s)
        with self.assertRaises(RuleError):apply(s,'human',{'type':'insert','position':999})
        self.assertEqual(s,before)
    def test_future_private_shuffle_and_draw_shift(self):
        s=rig_ek(['See the Future','Shuffle'],['Skip'],['Attack','Favor','Exploding Kitten'])
        s=settle(apply(s,'human',{'type':'play','card':'See the Future'}))
        self.assertEqual(s['private_knowledge']['human'][-1]['cards'],['Attack','Favor','Exploding Kitten'])
        self.assertFalse(any(k['kind']=='future' for k in projection(s,'ai')['private_knowledge']))
        drawn=apply(s,'human',{'type':'draw'})
        self.assertEqual(drawn['private_knowledge']['human'][-2]['cards'],['Favor','Exploding Kitten'])
        s=settle(apply(s,'human',{'type':'play','card':'Shuffle'}))
        self.assertFalse(s['private_knowledge']['human'][-1]['current']);validate(s)
    def test_attack_two_turns_skip_one_and_no_stack(self):
        s=rig_ek(['Attack','Skip'],['Attack','Skip'],['Favor','Shuffle'])
        s=settle(apply(s,'human',{'type':'play','card':'Attack'}))
        self.assertEqual(s['current_player'],'ai');self.assertEqual(s['turn_state']['turns_remaining'],2)
        s=settle(apply(s,'ai',{'type':'play','card':'Skip'}));self.assertEqual(s['turn_state']['turns_remaining'],1)
        s=settle(apply(s,'ai',{'type':'play','card':'Attack'}))
        self.assertEqual(s['current_player'],'human');self.assertEqual(s['turn_state']['turns_remaining'],2)
        s=apply(s,'human',{'type':'draw'});self.assertEqual(s['current_player'],'human')
        self.assertEqual(s['turn_state']['turns_remaining'],1)
        s=apply(s,'human',{'type':'draw'});self.assertEqual(s['current_player'],'ai')
    def test_favor_giver_chooses(self):
        s=rig_ek(['Favor'],['Defuse','Taco Cat'])
        s=settle(apply(s,'human',{'type':'play','card':'Favor'}));self.assertEqual(s['turn_state']['phase'],'favor')
        before=copy.deepcopy(s)
        with self.assertRaises(RuleError):apply(s,'human',{'type':'give','card':'Defuse'})
        self.assertEqual(s,before)
        s=apply(s,'ai',{'type':'give','card':'Taco Cat'})
        self.assertEqual([c['name'] for c in s['game_state']['hands']['human']],['Taco Cat'])
    def test_nope_and_nope_the_nope(self):
        base=rig_ek(['Attack','Nope'],['Nope'])
        s=apply(base,'human',{'type':'play','card':'Attack'});s=apply(s,'ai',{'type':'nope'});s=settle(s)
        self.assertEqual(s['current_player'],'human')
        s=apply(base,'human',{'type':'play','card':'Attack'});s=apply(s,'ai',{'type':'nope'});s=apply(s,'human',{'type':'nope'});s=settle(s)
        self.assertEqual(s['current_player'],'ai');self.assertEqual(len(s['game_state']['discards']),3)
    def test_nope_cannot_stop_draw_or_defuse(self):
        s=rig_ek(['Defuse','Nope'],['Nope'],['Exploding Kitten']);s=apply(s,'human',{'type':'draw'})
        with self.assertRaises(RuleError):apply(s,'ai',{'type':'nope'})
    def test_combo2_function_cards_random_steal_no_attack(self):
        s=rig_ek(['Attack','Attack'],['Skip','Defuse','Shuffle']);before=s['randomness_state']['counter']
        s=settle(apply(s,'human',{'type':'combo2','cards':['Attack']*2}))
        self.assertEqual(s['current_player'],'human');self.assertEqual(s['turn_state']['turns_remaining'],1)
        self.assertEqual(len(s['game_state']['hands']['human']),1);self.assertGreater(s['randomness_state']['counter'],before)
    def test_combo3_hit_miss(self):
        for target,expected in [('Defuse',1),('Skip',0)]:
            s=rig_ek(['Taco Cat']*3,['Defuse','Shuffle'])
            s=settle(apply(s,'human',{'type':'combo3','cards':['Taco Cat']*3,'request':target}))
            self.assertEqual(len(s['game_state']['hands']['human']),expected)
    def test_combo5_functions_allowed_own_discard_retrieval(self):
        cards=['Defuse','Attack','Skip','Favor','Taco Cat'];s=rig_ek(cards,['Nope'])
        s=settle(apply(s,'human',{'type':'combo5','cards':cards,'retrieve':'Defuse'}))
        self.assertEqual([c['name'] for c in s['game_state']['hands']['human']],['Defuse'])
        self.assertEqual(len(s['game_state']['discards']),4);validate(s)
    def test_combo5_repeated_name_illegal(self):
        s=rig_ek(['Defuse','Attack','Attack','Favor','Taco Cat'],[])
        with self.assertRaises(RuleError):apply(s,'human',{'type':'combo5','cards':['Defuse','Attack','Attack','Favor','Taco Cat'],'retrieve':'Defuse'})
    def test_combo_nope_consumes_all_cards_no_effect(self):
        s=rig_ek(['Attack','Attack'],['Nope','Defuse']);s=apply(s,'human',{'type':'combo2','cards':['Attack']*2})
        s=apply(s,'ai',{'type':'nope'});s=settle(s)
        self.assertEqual(len(s['game_state']['hands']['human']),0);self.assertEqual(len(s['game_state']['hands']['ai']),1)
    def test_empty_opponent_no_steal(self):
        s=rig_ek(['Taco Cat','Taco Cat'],[]);s=settle(apply(s,'human',{'type':'combo2','cards':['Taco Cat']*2}))
        self.assertEqual(len(s['game_state']['hands']['human']),0)
    def test_hand_counts_merge(self):
        s=rig_ek(['Attack','Attack','Defuse','Taco Cat','Taco Cat','Skip'],['Nope'])
        text=render(projection(s,'human'));self.assertIn('你的手牌（6张）',text);self.assertIn('攻击 ×2',text)
        self.assertIn('🐱塔可猫 ×2',text);self.assertIn('Null手牌：1张',text)

class IncanTests(unittest.TestCase):
    def test_2018_deck_and_artifacts(self):
        s=create('incan_gold',True,SEED,ruleset=ig.LEGACY_VERSION);self.assertEqual(len(ig.zones(s)),35)
        self.assertEqual([c['value'] for c in s['game_state']['future_artifacts']],[7,8,10,12]);validate(s)
    def test_treasure_distribution_and_path(self):
        s=rig_ig([('Treasure',7)]);g=s['game_state']
        self.assertEqual(g['loot'],{'human':3,'ai':3});self.assertEqual(g['path_gems'],1)
    def test_repeated_hazard_loss_and_removed_card(self):
        s=rig_ig([('Treasure',7),('Snakes',None),('Snakes',None)])
        for _ in range(2):
            ig.commit_ai(s,{'type':'continue'});s=apply(s,'human',{'type':'continue'})
        self.assertEqual(s['turn_state']['phase'],'round_end')
        self.assertEqual(s['game_state']['loot'],{'human':0,'ai':0})
        self.assertEqual(Counter(c['name'] for c in s['game_state']['removed']),{'Snakes':1});validate(s)
    def test_single_retreat_gems_artifact(self):
        s=rig_ig([('Artifact',5),('Treasure',7)])
        s['game_state']['loot']={'human':3,'ai':3};s['game_state']['path_gems']=1
        ig.commit_ai(s,{'type':'continue'});s=apply(s,'human',{'type':'return'})
        g=s['game_state'];self.assertEqual(g['bank']['human'],4);self.assertEqual(g['artifacts']['human'][0]['value'],5)
        self.assertEqual(g['loot']['ai'],10);validate(s)
    def test_simultaneous_retreat_no_artifact(self):
        s=rig_ig([('Artifact',5)]);s['game_state']['path_gems']=3
        ig.commit_ai(s,{'type':'return'});s=apply(s,'human',{'type':'return'})
        g=s['game_state'];self.assertEqual(g['bank'],{'human':1,'ai':1})
        self.assertFalse(any(g['artifacts'].values()));self.assertTrue(any(c['name']=='Artifact' for c in g['removed']))
    def test_ai_solo_return_and_bank_unchanged_after_disaster(self):
        s=rig_ig([('Treasure',7),('Snakes',None),('Snakes',None)])
        ig.commit_ai(s,{'type':'return'});s=apply(s,'human',{'type':'continue'})
        self.assertEqual(s['game_state']['bank']['ai'],4)
        s=apply(s,'human',{'type':'continue'});self.assertEqual(s['game_state']['bank']['ai'],4)
        self.assertEqual(s['game_state']['loot']['human'],0)
    def test_commit_before_input_and_no_secret_in_projections(self):
        s=rig_ig([('Treasure',7)]);before=copy.deepcopy(s)
        with self.assertRaises(RuleError):apply(s,'human',{'type':'return'})
        self.assertEqual(s,before)
        ig.commit_ai(s,{'type':'continue'});c=s['turn_state']['commitment']
        for p in ('human','ai'):
            v=projection(s,p);self.assertNotIn(c['nonce'],json.dumps(v));self.assertNotIn('commitment',v['public'])
            self.assertEqual(v['ai_commitment_sha256'],c['sha256'])
        s=apply(s,'human',{'type':'return'});r=s['public_state']['last_reveal']
        payload='%s:%d:%d:%s:%s'%(r['session_id'],r['round'],r['decision_number'],r['choice'],r['nonce'])
        self.assertEqual(hashlib.sha256(payload.encode()).hexdigest(),r['sha256'])
    def test_unfound_artifact_carries_to_next_round(self):
        s=rig_ig([('Treasure',7)]);ig.commit_ai(s,{'type':'return'});s=apply(s,'human',{'type':'return'})
        self.assertTrue(any(c['name']=='Artifact' and c['value']==5 for c in s['game_state']['deck']))
        s=apply(s,'human',{'type':'next_round'});self.assertEqual(s['game_state']['round'],2);validate(s)
    def test_final_scoring_tiebreak_artifact_count(self):
        s=create('incan_gold',True,SEED);g=s['game_state']
        # Transfer all future artifacts into legal zones when moving fixture to round 5.
        g['round']=5;g['deck'].extend(g['future_artifacts']);g['future_artifacts']=[]
        g['deck'].extend(g['path']);g['path']=[]
        a=next(c for c in g['deck'] if c['name']=='Artifact' and c['value']==5);g['deck'].remove(a)
        g['artifacts']['human']=[a];g['bank']={'human':5,'ai':10}
        ig.end_round(s);validate(s);self.assertEqual(g['scores'],{'human':10,'ai':10});self.assertEqual(g['winners'],['human'])

class IsolationPersistenceLanguageTests(unittest.TestCase):
    def test_ai_view_hidden_state_noninterference(self):
        for game in ('love_letter','exploding_kittens'):
            s=create(game,True,SEED);g=s['game_state'];a=projection(s,'ai')
            modified=copy.deepcopy(s);h=modified['game_state']
            # Swap hidden identities without changing any public counts.
            h['hands']['human'][0],h['deck'][-1]=h['deck'][-1],h['hands']['human'][0]
            h['deck'].reverse();modified['randomness_state']['key']='ff'*32
            self.assertEqual(projection(modified,'ai'),a)
            for forbidden in ('game_state','randomness_state','deck','reserve','hands','human_hand'):
                self.assertNotIn(forbidden,a)
            self.assertEqual(a['opponent_hand_count'],len(g['hands']['human']))
    def test_human_cannot_see_ai_remaining_hand_or_future(self):
        s=rig_ek(['Taco Cat'],['Defuse','See the Future'],['Exploding Kitten','Skip','Attack'])
        s['current_player']='ai';s=settle(apply(s,'ai',{'type':'play','card':'See the Future'}))
        v=projection(s,'human');self.assertEqual(v['your_hand'],['Taco Cat'])
        self.assertEqual(v['private_knowledge'],[]);self.assertNotIn('future',json.dumps(v['private_knowledge']))
        self.assertNotIn('拆弹 ×',render(v));self.assertNotIn('爆炸猫 →',render(v))
    def test_subprocess_accepts_ai_view_only(self):
        s=create('love_letter',True,SEED)
        with self.assertRaises(RuleError):ask_ai(projection(s,'human'))
        s=apply(s,'human',ll.legal(s,'human')[0]);v=projection(s,'ai')
        if v['legal_actions']:self.assertIn(ask_ai(v),v['legal_actions'])
    def test_sqlite_restart_rng_and_hidden_choice_persistence(self):
        for game in ('love_letter','exploding_kittens','incan_gold'):
            with tempfile.TemporaryDirectory() as root:
                s=pump(create(game,True,SEED));db=Store(root)
                with db.transaction():db.save('t',s)
                db.close();db=Store(root);loaded=db.active('t');self.assertEqual(loaded,s)
                self.assertEqual(loaded['randomness_state'],s['randomness_state']);db.close()
    def test_illegal_no_rng_state_change(self):
        s=create('exploding_kittens',True,SEED);before=copy.deepcopy(s)
        with self.assertRaises(RuleError):human_action(s,{'type':'insert','position':0})
        self.assertEqual(s,before)
    def test_parser_examples(self):
        s=rig_ll(['Handmaid','Guard'],['Prince'])
        self.assertEqual(parse(s,'我出侍女'),{'type':'play','card':'Handmaid'})
        self.assertEqual(parse(s,'我猜你是男爵')['guess'],'Baron')
        with self.assertRaises(RuleError):parse(s,'我出卫兵')
        s=rig_ek(['Attack','Attack'],['Skip'])
        self.assertEqual(parse(s,'两张攻击偷你的牌'),{'type':'combo2','cards':['Attack','Attack']})
        self.assertEqual(parse(s,'两张Taco Cat偷你的牌')['cards'],['Taco Cat','Taco Cat'])
        self.assertEqual(parse(s,'我什么都不出，直接抽'),{'type':'draw'})
        self.assertEqual(parse(s,'三张Taco Cat索要拆弹')['request'],'Defuse')
        s=create('incan_gold',True,SEED)
        self.assertEqual(parse(s,'我继续往里面走'),{'type':'continue'})
        self.assertEqual(parse(s,'我怂了，带钱跑路'),{'type':'return'})
    def test_cli_idempotency_and_active_game_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            base=[sys.executable,str(SCRIPTS/'play.py'),'--data-dir',root,'--table','t','--json']
            def cli(extra):return json.loads(subprocess.run(base+extra,capture_output=True,text=True).stdout)
            a=cli(['--request-id','start','new','love_letter']);sid=a['view']['session_id']
            b=cli(['--request-id','start','new','love_letter']);self.assertEqual(a,b)
            c=cli(['chat','--text','来一局爆炸猫']);self.assertFalse(c['ok']);self.assertEqual(c['view']['session_id'],sid)
            d=cli(['debug']);self.assertFalse(d['ok']);self.assertNotIn('debug_state',d)
            status=cli(['status']);self.assertEqual(status['view']['revision'],a['view']['revision'])
            stale=cli(['--revision','999','chat','--text','我出侍女']);self.assertFalse(stale['ok'])
    def test_production_reject_seed(self):
        with self.assertRaises(RuleError):create('love_letter',False,SEED)

class RegressionTests(unittest.TestCase):
    def test_negative_nope_is_pass(self):
        s=rig_ek(['Attack','Nope'],['Nope'])
        s=apply(s,'human',{'type':'play','card':'Attack'});s=apply(s,'ai',{'type':'nope'})
        self.assertEqual(parse(s,'我不否决'),{'type':'pass'})
        after=apply(s,'human',parse(s,'我不否决'))
        self.assertTrue(any(c['name']=='Nope' for c in after['game_state']['hands']['human']))
    def test_negative_retreat_rejected(self):
        s=create('incan_gold',True,'readable-seed')
        before=copy.deepcopy(s)
        with self.assertRaises(RuleError):parse(s,'我不想返回营地，我想留下')
        self.assertEqual(s,before)
    def test_continue_expedition_not_new_game(self):
        from duo.language import game_intent
        self.assertIsNone(game_intent('我继续探险'))
        self.assertEqual(game_intent('我们去探险'),'incan_gold')
        s=create('incan_gold',True,SEED)
        self.assertEqual(parse(s,'我继续探险'),{'type':'continue'})
    def test_synchronous_proof_survives_ai_solo(self):
        s=rig_ig([('Treasure',7),('Treasure',17)])
        s=pump(s,chooser=lambda v:{'type':'continue'})
        commitment=copy.deepcopy(s['turn_state']['commitment'])
        s=apply(s,'human',{'type':'return'})
        s=pump(s,chooser=lambda v:{'type':'return'})
        self.assertEqual(projection(s,'human')['last_reveal']['sha256'],commitment['sha256'])
        self.assertEqual(len(projection(s,'human')['reveal_history']),2)
    def test_priest_historical_observation_is_displayed(self):
        s=rig_ll(['Priest','Princess'],['King'])
        s=apply(s,'human',{'type':'play','card':'Priest','target':'ai'})
        text=render(projection(s,'human'))
        self.assertIn('Null当时持有国王',text)
        self.assertIn('不能确定当前手牌',text)
    def test_arbitrary_debug_seed(self):
        a=create('love_letter',True,'seed-1');b=create('love_letter',True,'seed-1')
        self.assertEqual(a['game_state']['hands'],b['game_state']['hands'])
        self.assertEqual(a['randomness_state']['key'],b['randomness_state']['key'])
    def test_negated_ek_draw_give_insert_combos_rejected(self):
        for phase,phrase in [('play','我不要抽牌'),('play','我不出两张攻击偷牌'),('favor','我不给拆弹'),('insert','不要放在顶部')]:
            s=rig_ek(['Attack','Attack','Defuse'],['Favor'],['Exploding Kitten'])
            if phase=='insert':s=apply(s,'human',{'type':'draw'})
            elif phase=='favor':
                s['current_player']='ai'
                s=settle(apply(s,'ai',{'type':'play','card':'Favor'}))
            before=copy.deepcopy(s)
            with self.assertRaises(RuleError):parse(s,phrase)
            self.assertEqual(s,before)
        s=create('exploding_kittens',True,SEED)
        self.assertEqual(parse(s,'我什么都不出，直接抽'),{'type':'draw'})
        self.assertEqual(parse(s,'我不出牌，直接抽'),{'type':'draw'})
        with self.assertRaises(RuleError):parse(s,'我不出牌也不抽牌')
    def test_negated_switch_does_not_abandon_or_start(self):
        with tempfile.TemporaryDirectory() as root:
            base=[sys.executable,str(SCRIPTS/'play.py'),'--data-dir',root,'--table','t','--json']
            def cli(extra):return json.loads(subprocess.run(base+extra,capture_output=True,text=True).stdout)
            a=cli(['new','love_letter','--debug','--seed','stay'])
            b=cli(['chat','--text','我不要结束当前游戏并开始爆炸猫'])
            self.assertFalse(b['ok']);self.assertEqual(b['view']['session_id'],a['view']['session_id'])
            self.assertEqual(b['view']['revision'],a['view']['revision'])
            self.assertEqual(cli(['status'])['view'],a['view'])
    def test_malformed_action_returns_public_error_only(self):
        with tempfile.TemporaryDirectory() as root:
            base=[sys.executable,str(SCRIPTS/'play.py'),'--data-dir',root,'--table','t','--json']
            def cli(extra):return json.loads(subprocess.run(base+extra,capture_output=True,text=True).stdout)
            a=cli(['new','exploding_kittens'])
            for payload in ('[]','null','{"type":"combo2","cards":null}'):
                b=cli(['action','--action',payload]);self.assertFalse(b['ok'])
                self.assertEqual(b['view']['revision'],a['view']['revision'])
    def test_hypothetical_action_is_not_executed(self):
        from duo.language import game_intent
        s=create('exploding_kittens',True,SEED)
        with self.assertRaises(RuleError):parse(s,'如果我攻击会怎么样')
        self.assertIsNone(game_intent('如果结束当前游戏并开始爆炸猫'))

    def test_negative_play_no_mutation(self):
        for game,phrase in [('love_letter','不要出侍女'),('exploding_kittens','我不打攻击')]:
            s=create(game,True,SEED)
            with self.assertRaises(RuleError):parse(s,phrase)

class FullGameTests(unittest.TestCase):
    def test_acceptance_complete_games(self):
        self.completed=[]
        human_rng=random.Random(20261007)
        for game, count in [('love_letter',3),('exploding_kittens',2),('incan_gold',1)]:
            for n in range(count):
                s=pump(create(game,True,('%02x'%(n+11))*32));steps=0
                while s['status']=='active' and steps<3000:
                    actions=projection(s,'human')['legal_actions']
                    self.assertTrue(actions,(game,s['turn_state']))
                    if game=='love_letter':
                        action=human_rng.choice(actions)
                        # Avoid trivially throwing the whole match by always discarding Princess.
                        good=[a for a in actions if a.get('card')!='Princess']
                        if good:action=human_rng.choice(good)
                    elif game=='exploding_kittens':
                        phase=s['turn_state']['phase']
                        if phase=='play':
                            options=[a for a in actions if a['type']=='draw' or (a['type']=='play' and a['card'] in ('Attack','Skip','Favor','See the Future','Shuffle')) or a['type'] in ('combo2','combo3','combo5')]
                            action=human_rng.choice(options)
                        elif phase=='response':action=human_rng.choice(actions)
                        else:action=human_rng.choice(actions)
                    else:
                        action={'type':'next_round'} if s['turn_state']['phase']=='round_end' else human_rng.choice(actions)
                    s=human_action(s,action);validate(s)
                    view=projection(s,'human')
                    if 'your_hand' in view:self.assertEqual(len(view['your_hand']),len(s['game_state']['hands']['human']))
                    steps+=1
                self.assertEqual(s['status'],'finished',(game,steps))
                if game=='love_letter':self.assertGreaterEqual(max(s['game_state']['scores'].values()),7)
                if game=='incan_gold':self.assertEqual(s['game_state']['round'],5)
                self.completed.append({'game':game,'game_number':n+1,'steps':steps,'rounds':s['game_state'].get('round'), 'winners':s['game_state']['winners']})
        print('\nACCEPTANCE_GAMES='+json.dumps(self.completed,ensure_ascii=False))

if __name__=='__main__':unittest.main(verbosity=2)
