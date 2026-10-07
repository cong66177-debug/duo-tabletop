#!/usr/bin/env python3
"""The sole production chat entry point. Never exposes a raw Game State or AI hand."""
import argparse
import copy
import hashlib
import json
import os
import sys
import sqlite3
import re
from pathlib import Path

from duo.common import RuleError, StateError, Randomness, require
from duo.engine import create, human_action, projection, pump
from duo.language import game_intent, normalize, parse
from duo.render import render, TITLES
from duo.store import Store
from duo.visibility import visible
from duo import kittens as ek
from duo.qa import output as check_output

def result(s, before=0, error=None):
    v = projection(s,'human') if s else None
    if v: check_output(s,v)
    events = [e for e in s['public_state']['events'][before:] if visible(e,'human')] if s else []
    text = render(v, events) if v else '选择一个游戏：情书 / 爆炸猫 / 印加宝藏。'
    return {'ok': error is None, 'error': error, 'view': v, 'output_contract':2,
            'text': ((error+'\n\n') if error else '')+text}

def run(args):
    store = Store(args.data_dir)
    try:
        with store.transaction():
            # A frozen table cannot replay cached narrative and appear to continue.
            try: s = store.active(args.table)
            except StateError:
                if args.command == 'new' and args.replace:
                    store.clear_fault(args.table); s = None
                else: raise
            cached = store.previous_result(args.table,args.request_id)
            if cached is not None: return cached
            original = copy.deepcopy(s)
            before = len(s['public_state']['events']) if s else 0
            try:
                if args.revision is not None and s:
                    require(s['revision'] == args.revision, '存档已更新，请先查看当前状态，再提交这次动作。')
                if args.command == 'status': return result(s, max(0,before-8))
                if args.command == 'debug':
                    require(s is not None and s['mode']=='debug', '正式局没有Debug读取接口。需要另开显式DEBUG测试局。')
                    return {'ok':True,'debug_state':s,'text':'DEBUG完整状态：\n'+json.dumps(s,ensure_ascii=False,indent=2)}
                game = args.game
                text = args.text or ''
                if args.command == 'chat':
                    t = normalize(text)
                    if re.search(r'如果|假如|假设|举例|例如|if |suppose ',t):
                        raise RuleError('这是规则咨询或假设语句，未提交动作或更换会话。')
                    if re.search(r'不|别|没|don.t|not ',t) and any(x in t for x in ('开始','结束','新游戏','重开','start','new game')):
                        raise RuleError('启动或结束游戏的语句带有否定，当前会话未更换。请明确是否继续或开新游戏。')
                    if t in ('状态','手牌','看看手牌','查看状态','继续游戏','恢复游戏','status'):
                        return result(s,max(0,before-8))
                    if s and s['game_type']=='exploding_kittens' and re.search(r'效果|怎么用|有什么用|作用|介绍|解释|是什么|干什么|能干嘛|用途|如何使用',t):
                        from duo.language import mentions
                        names = mentions(t,ek.COUNTS)
                        require(bool(names),'请指定要了解的牌名。')
                        out = result(s,before)
                        from collections import Counter
                        counts = Counter(out['view']['your_hand'])
                        out['text'] = '\n'.join('%s%s ×%d：%s' % (ek.EMOJI[n],ek.LABEL[n],counts[n],ek.EFFECT[n]) for n in names)+'\n\n'+out['text']
                        return out
                    game = game_intent(text)
                    if t in ('开始新游戏','新游戏','重开','new game') and s: game = s['game_type']
                    if any(x in t for x in ('来玩桌游','来玩一局桌游','玩桌游')) and not game:
                        return result(s,max(0,before-8))
                if args.command == 'new' or game:
                    if s and s['status']=='active':
                        explicit = args.replace or ('结束' in text and ('开始' in text or '新' in text))
                        require(explicit, '当前还有一局%s。可继续，或明确说“结束当前游戏并开始%s”。' % (TITLES[s['game_type']],TITLES[game]))
                        # Keep the previous session in history; ending it never deletes it.
                        ended = copy.deepcopy(s); ended['status']='abandoned'; ended['revision']+=1
                        store.save(args.table,ended)
                    require(args.seed is None or args.debug, '正式模式不能指定种子。')
                    s = pump(create(game,args.debug,args.seed)); before = 0
                    store.save(args.table,s)
                    out = result(s,before)
                else:
                    require(s is not None, '还没有游戏。说“来一局情书”“来一局爆炸猫”或“我们去探险”。')
                    require(s['status']=='active','本局已结束。说“开始新游戏”重开。')
                    if args.command == 'action':
                        try: action = json.loads(args.action)
                        except ValueError: raise RuleError('动作JSON格式错误。')
                    else: action = parse(s,text)
                    require(isinstance(action,dict),'动作必须是一个JSON对象。')
                    if action.get('type') == 'insert_random':
                        # Do this on a copy; an illegal random insertion cannot consume RNG state.
                        require(s['game_type']=='exploding_kittens' and s['turn_state']['phase']=='insert' and s['current_player']=='human','当前不是你的秘密插回阶段。')
                        s = copy.deepcopy(s)
                        position = Randomness(s['randomness_state']).below(len(s['game_state']['deck'])+1,'human-random-insert')
                        action = {'type':'insert','position':position}
                    s = human_action(s,action); store.save(args.table,s); out = result(s,before)
                store.record_result(args.table,args.request_id,out)
                return out
            except StateError: raise
            except RuleError as e:
                # Roll back any partial save (including abandoning a previous session).
                store.db.rollback(); store.db.execute('BEGIN IMMEDIATE')
                return result(original, before, str(e))
    except StateError:
        store.freeze(args.table)
        return {'ok':False,'error':'状态校验失败','paused':True,'view':None,'output_contract':2,
                'text':'状态校验失败：本桌已暂停。未补牌、删牌或继续行动；保留原存档供修复。'}
    finally: store.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default=str(Path.home()/'Documents'/'Codex'/'duo-tabletop-data'))
    parser.add_argument('--table', default='cwd-'+hashlib.sha256(str(Path.cwd()).encode()).hexdigest()[:20])
    parser.add_argument('--json', action='store_true', help='Human View only; production output is never full state.')
    parser.add_argument('--request-id', help='Unique user-message ID; retries return previous result without re-executing.')
    parser.add_argument('--revision', type=int, help='Expected revision for stale-command rejection.')
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('status'); sub.add_parser('debug')
    chat = sub.add_parser('chat'); chat.add_argument('--text',required=True)
    new = sub.add_parser('new'); new.add_argument('game',choices=['love_letter','exploding_kittens','incan_gold'])
    new.add_argument('--replace',action='store_true'); new.add_argument('--debug',action='store_true'); new.add_argument('--seed')
    action = sub.add_parser('action'); action.add_argument('--action',required=True)
    args = parser.parse_args()
    for k, default in (('text',None),('game',None),('replace',False),('debug',False),('seed',None),('action',None)):
        if not hasattr(args,k): setattr(args,k,default)
    try: out = run(args)
    except (OSError,ValueError,sqlite3.Error) as e:
        # Deliberately do not print exception args, paths, raw database contents, or traceback.
        out = {'ok':False,'error':'本地引擎或存档读取失败，未提交动作。请在测试环境排查。','text':'本地引擎或存档读取失败，未提交动作。'}
    print(json.dumps(out,ensure_ascii=False) if args.json else out['text'])
    return 0 if out['ok'] else 2

if __name__ == '__main__': sys.exit(main())
