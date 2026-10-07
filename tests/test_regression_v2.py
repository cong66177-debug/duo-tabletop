"""Regression contracts from real play; fixtures use conserved physical cards."""
import copy
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from test_games import rig_ll, rig_ek, rig_ig, settle, SEED, SCRIPTS
from duo import incan as ig, kittens as ek
from duo.common import StateError, event, private
from duo.engine import create, apply, projection, ask_ai, pump, validate, human_action
from duo.render import render
from duo.store import Store
from duo.visibility import migrate, audit_view

class InformationRegression(unittest.TestCase):
    def test_each_visibility_is_filtered_before_render_and_worker(self):
        s=create('love_letter',True,SEED)
        for tag in ('PUBLIC','PLAYER_ONLY','NULL_ONLY','HOST_ONLY'):
            event(s,tag+'-canary',visibility=tag)
        h=projection(s,'human'); n=projection(s,'ai')
        self.assertIn('PLAYER_ONLY-canary',render(h))
        self.assertNotIn('NULL_ONLY-canary',json.dumps(h));self.assertNotIn('HOST_ONLY-canary',json.dumps(h))
        self.assertNotIn('PLAYER_ONLY-canary',json.dumps(n));self.assertNotIn('HOST_ONLY-canary',json.dumps(n))
        self.assertIn('PUBLIC-canary',h['events']);self.assertIn('PUBLIC-canary',n['events'])
    def test_guard_policy_independent_of_hidden_hand_and_deck(self):
        s=rig_ll(['Prince'],['Guard','King']);s['current_player']='ai'
        before=projection(s,'ai'); action=ask_ai(before)
        self.assertEqual(action['card'],'Guard')
        changed=copy.deepcopy(s);g=changed['game_state']
        i=next(i for i,c in enumerate(g['deck']) if c['name']=='Princess')
        g['hands']['human'][0],g['deck'][i]=g['deck'][i],g['hands']['human'][0]
        g['deck'].reverse();changed['randomness_state']['key']='ab'*32
        self.assertEqual(projection(changed,'ai'),before)
        self.assertEqual(ask_ai(projection(changed,'ai')),action)
    def test_null_normal_draw_never_names_card_to_player(self):
        s=rig_ek(['Nope'],['Skip'],['Hairy Potato Cat']);s['current_player']='ai'
        before=len(s['public_state']['events']);s=apply(s,'ai',{'type':'draw'})
        v=projection(s,'human');text=render(v,v['event_records'])
        self.assertIn('Null摸了1张牌，没有爆炸',text)
        self.assertNotIn('毛茸茸猫',text);self.assertNotIn('Hairy Potato Cat',json.dumps(v))
        self.assertEqual(s['game_state']['hands']['ai'][-1]['name'],'Hairy Potato Cat')
        self.assertEqual(v['opponent_hand_count'],2)
    def test_null_future_is_never_in_player_view(self):
        s=rig_ek(['Nope'],['See the Future'],['Hairy Potato Cat','Skip','Attack']);s['current_player']='ai'
        s=settle(apply(s,'ai',{'type':'play','card':'See the Future'}))
        self.assertNotIn('Hairy Potato Cat',json.dumps(projection(s,'human')))
        self.assertEqual(projection(s,'ai')['private_knowledge'][-1]['cards'],['Hairy Potato Cat','Skip','Attack'])
    def test_shuffle_invalidates_both_then_draw_shifts_only_known_prefix(self):
        s=rig_ek(['Shuffle'],['Nope'],['Attack','Skip','Favor'])
        for p in ('human','ai'):private(s,p,'future',cards=['Attack','Skip','Favor'],epoch=0,current=True)
        d=apply(s,'human',{'type':'draw'})
        for p in ('human','ai'):self.assertEqual(d['private_knowledge'][p][0]['cards'],['Skip','Favor'])
        s=settle(apply(s,'human',{'type':'play','card':'Shuffle'}))
        self.assertFalse(any(k.get('current') for ks in s['private_knowledge'].values() for k in ks));validate(s)
    def test_missing_permission_or_cross_owner_is_failure(self):
        s=create('love_letter',True,SEED);s['public_state']['events'].append({'text':'canary'})
        with self.assertRaises(StateError):projection(s,'human')
        s=create('love_letter',True,SEED);private(s,'human','draw',card='Guard',current=False)
        s['private_knowledge']['human'][0]['visibility']='NULL_ONLY'
        with self.assertRaises(StateError):projection(s,'human')
    def test_renderer_rejects_ai_view_and_unapproved_narration(self):
        s=create('love_letter',True,SEED)
        with self.assertRaises(StateError):render(projection(s,'ai'))
        with self.assertRaises(StateError):render(projection(s,'human'),[{'text':'invented','visibility':'PUBLIC'}])
    def test_view_rejects_host_fields_and_wrong_labels(self):
        v=projection(create('love_letter',True,SEED),'human');v['game_state']={'secret':1}
        with self.assertRaises(StateError):audit_view(v)

class TurnAndPolicyRegression(unittest.TestCase):
    def test_known_bomb_without_defuse_uses_each_available_escape(self):
        for escape in ('Skip','Attack','Shuffle'):
            s=rig_ek(['Nope'],[escape,'Taco Cat','Taco Cat'],['Exploding Kitten']);s['current_player']='ai'
            private(s,'ai','future',cards=['Exploding Kitten'],epoch=0,current=True)
            self.assertEqual(ask_ai(projection(s,'ai')),{'type':'play','card':escape})
    def test_unknown_bomb_does_not_change_null_policy(self):
        s=rig_ek(['Nope'],['Skip'],['Exploding Kitten']);s['current_player']='ai'
        safe=copy.deepcopy(s);g=safe['game_state'];i=next(i for i,c in enumerate(g['deck']) if c['name']=='Taco Cat')
        g['deck'][0],g['deck'][i]=g['deck'][i],g['deck'][0]
        self.assertEqual(ask_ai(projection(s,'ai')),ask_ai(projection(safe,'ai')))
    def test_pair_and_triple_do_not_end_turn(self):
        for action in ({'type':'combo2','cards':['Taco Cat']*2},
                       {'type':'combo3','cards':['Taco Cat']*3,'request':'Defuse'}):
            s=rig_ek(['Taco Cat']*3,['Defuse']);s['turn_state']['turns_remaining']=2
            s=settle(apply(s,'human',action))
            self.assertEqual(s['current_player'],'human');self.assertEqual(s['turn_state']['turns_remaining'],2)
            self.assertEqual(s['turn_state']['phase'],'play');self.assertIn({'type':'draw'},projection(s,'human')['legal_actions'])
    def test_attack_first_turn_can_play_then_skip_then_second_draw(self):
        s=rig_ek(['Attack'],['Skip','See the Future'],['Taco Cat','Cattermelon'])
        s=settle(apply(s,'human',{'type':'play','card':'Attack'}));self.assertEqual(s['turn_state']['turns_remaining'],2)
        s=settle(apply(s,'ai',{'type':'play','card':'See the Future'}));self.assertEqual(s['turn_state']['turns_remaining'],2)
        s=settle(apply(s,'ai',{'type':'play','card':'Skip'}));self.assertEqual(s['current_player'],'ai');self.assertEqual(s['turn_state']['turns_remaining'],1)
        s=apply(s,'ai',{'type':'draw'});self.assertEqual(s['current_player'],'human')
    def test_all_null_functions_stop_for_human_response(self):
        for card in ek.FUNCTIONS:
            s=rig_ek(['Nope'],[card]);s['current_player']='ai'
            s=pump(s,chooser=lambda v:{'type':'play','card':card})
            self.assertEqual(s['turn_state']['phase'],'response');self.assertEqual(s['turn_state']['responder'],'human')
            self.assertIn({'type':'nope'},projection(s,'human')['legal_actions'])
            self.assertIn('尚未结算',render(projection(s,'human')))
    def test_three_nope_chain_cancels_attack(self):
        s=rig_ek(['Attack','Nope'],['Nope','Nope'])
        s=apply(s,'human',{'type':'play','card':'Attack'})
        for p in ('ai','human','ai'):s=apply(s,p,{'type':'nope'})
        s=settle(s);self.assertEqual(s['current_player'],'human');self.assertEqual(s['turn_state']['turns_remaining'],1)
    def test_five_combo_must_use_five_distinct_real_cards(self):
        s=rig_ek(['Taco Cat']*4+['Skip'],['Nope']);before=copy.deepcopy(s)
        with self.assertRaises(Exception):apply(s,'human',{'type':'combo5','cards':['Taco Cat']*4+['Skip'],'retrieve':'Skip'})
        self.assertEqual(s,before)

class StateAndIncanRegression(unittest.TestCase):
    def test_first_claimed_artifact_scores_its_random_card_value(self):
        s=create('incan_gold',True,SEED);g=s['game_state']
        pool=g['deck']+g['path']+g['future_artifacts']
        artifact=next(c for c in pool if c['name']=='Artifact' and c['value']==8)
        future=[c for c in pool if c['name']=='Artifact' and c is not artifact]
        g.update(deck=[artifact]+[c for c in pool if c['name']!='Artifact'],path=[],future_artifacts=future,
                 hazards={},path_gems=0,loot={'human':0,'ai':0})
        s['turn_state'].update(phase='reveal',decision_number=0,commitment=None)
        ig.reveal(s);ig.commit_ai(s,{'type':'continue'})
        s=apply(s,'human',{'type':'return'});v=projection(s,'human')
        self.assertEqual(v['public']['artifacts']['human'],[8]);self.assertEqual(v['your_score'],8)

    def test_artifact_random_entry_keeps_card_values_and_hides_unrevealed(self):
        orders=set()
        for seed in range(12):
            s=create('incan_gold',True,str(seed));g=s['game_state']
            artifacts=[c for c in ig.zones(s) if c['name']=='Artifact']
            self.assertEqual(sorted(c['value'] for c in artifacts),[5,7,8,10,12])
            orders.add(tuple(c['value'] for c in g['future_artifacts']))
            v=projection(s,'human');self.assertNotIn('future_artifacts',json.dumps(v))
            self.assertIn('秘密加入一张遗物',render(v))
            self.assertNotIn('加入价值',render(v))
        self.assertGreater(len(orders),1)
    def test_same_debug_seed_artifact_order_reproducible(self):
        a=create('incan_gold',True,'entry');b=create('incan_gold',True,'entry')
        self.assertEqual(a['game_state'],b['game_state'])
    def test_commitment_cannot_be_recomputed_or_revealed_differently(self):
        s=rig_ig([('Treasure',7)]);ig.commit_ai(s,{'type':'continue'});before=copy.deepcopy(s)
        with self.assertRaises(Exception):ig.commit_ai(s,{'type':'return'})
        self.assertEqual(s,before)
        with self.assertRaises(StateError):ig.decisions(copy.deepcopy(s),{'human':'return','ai':'return'})
        corrupt=copy.deepcopy(s);corrupt['turn_state']['commitment']['choice']='return'
        with self.assertRaises(StateError):projection(corrupt,'human')
    def test_player_return_does_not_end_null_solo_exploration(self):
        s=rig_ig([('Treasure',7),('Treasure',17),('Snakes',None),('Snakes',None)])
        ig.commit_ai(s,{'type':'continue'});s=apply(s,'human',{'type':'return'})
        self.assertEqual(s['game_state']['active'],['ai']);self.assertEqual(s['turn_state']['phase'],'decision')
        bank=s['game_state']['bank']['human'];s=pump(s,chooser=lambda v:{'type':'continue'})
        self.assertEqual(s['turn_state']['phase'],'round_end');self.assertEqual(s['game_state']['bank']['human'],bank)
    def test_card_conservation_identity_values_and_counts_detected(self):
        for game in ('love_letter','exploding_kittens','incan_gold'):
            for flaw in ('missing','duplicate','id','count'):
                s=create(game,True,SEED);g=s['game_state']
                if flaw=='missing':g['deck'].pop()
                if flaw=='duplicate':g['deck'].append(g['deck'][0])
                if flaw=='id':g['deck'][0]['id']='counterfeit'
                if flaw=='count':g['deck_count']=len(g['deck'])+1
                with self.assertRaises(StateError):projection(s,'human')
        s=create('incan_gold',True,SEED);next(c for c in ig.zones(s) if c['name']=='Artifact')['value']=999
        with self.assertRaises(StateError):validate(s)
    def test_bad_knowledge_and_pending_phase_stop_output(self):
        s=rig_ek(['Nope'],['Skip'],['Attack']);private(s,'human','future',cards=['Skip'],epoch=0,current=True)
        with self.assertRaises(StateError):projection(s,'human')
        s=create('exploding_kittens',True,SEED);s['turn_state']['phase']='response'
        with self.assertRaises(StateError):projection(s,'human')
    def test_legacy_schema_preserves_hidden_state_rng_and_rules(self):
        s=create('incan_gold',True,SEED,ruleset=ig.LEGACY_VERSION);s=pump(s)
        old=copy.deepcopy(s);old['schema_version']=1;old.pop('visibility')
        old['public_state']['events']=[e['text'] for e in old['public_state']['events']]
        for ks in old['private_knowledge'].values():
            for k in ks:k.pop('visibility',None)
        new=migrate(old);validate(new)
        for key in ('game_state','randomness_state','turn_state','ruleset_version','revision'):self.assertEqual(new[key],s[key])
        self.assertEqual(new['ruleset_version'],ig.LEGACY_VERSION)
    def test_corrupt_cli_table_pauses_and_preserves_bad_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            s=create('exploding_kittens',True,SEED);db=Store(root)
            with db.transaction():db.save('t',s)
            s['game_state']['deck'].pop();body=json.dumps(s)
            db.db.execute('UPDATE sessions SET body=? WHERE id=?',(body,s['session_id']));db.db.commit();db.close()
            base=[sys.executable,str(SCRIPTS/'play.py'),'--data-dir',root,'--table','t','--json']
            for cmd in (['status'],['chat','--text','直接抽牌']):
                r=json.loads(subprocess.run(base+cmd,capture_output=True,text=True).stdout)
                self.assertTrue(r['paused']);self.assertIsNone(r['view']);self.assertIn('状态校验失败',r['text'])
            db=sqlite3.connect(str(Path(root)/'sessions.sqlite3'))
            self.assertEqual(db.execute('SELECT body FROM sessions WHERE id=?',(s['session_id'],)).fetchone()[0],body);db.close()
    def test_rule_help_and_initial_counts_are_read_only_and_compact(self):
        with tempfile.TemporaryDirectory() as root:
            base=[sys.executable,str(SCRIPTS/'play.py'),'--data-dir',root,'--table','t','--json']
            def cli(args):return json.loads(subprocess.run(base+args,capture_output=True,text=True).stdout)
            a=cli(['new','exploding_kittens']);v=a['view']
            self.assertEqual(len(v['your_hand']),5);self.assertEqual(v['opponent_hand_count'],5);self.assertEqual(v['public']['deck_count'],41)
            b=cli(['chat','--text','攻击怎么用']);self.assertEqual(a['view'],b['view']);self.assertIn('两个完整回合',b['text'])
            self.assertIn('🧯拆弹 ×1',a['text'])

if __name__ == '__main__':unittest.main()
