# 架构、能力边界及扩展

## 数据流

```text
用户自然语言 → play.py → 保守意图解析 → 人类动作
                                    ↓
                         SQLite事务内规则引擎
                         ├─ 私有Game State / RNG
                         ├─ Human View → 聊天展示
                         └─ AI Player View → ai_player.py隔离进程 → 验证后执行
```

聊天模型仅作为用户接口，不能参与Null决策，因为它的聊天上下文包含Human View。Null是有策略的程序玩家：情书按公开牌数与合法私下观察评估牌效；爆炸猫保留拆弹、使用组合、预知危险、选择否决；印加按公开危险概率及未带回财富调整风险。这不是第二个ChatGPT模型。叙事由固定事件生成，personality.py在规则/状态/权限检查通过后从已过滤事件生成台词，主聊天原样展示。

`ai_player.py`只从stdin读JSON，输出动作JSON，无存档路径、Game State、完整牌堆、用户原话、Human View、随机源、其他玩家私人知识。`projection()`按允许字段新建视图，不是把完整状态交给AI后再要求不看。`ask_ai()`以隔离Python导入、临时空cwd、精简环境运行worker；无自由解释文本可泄露剩余手牌。动作由引擎再次核合法。

这是真正的数据传参隔离，但不是对恶意修改worker代码的OS权限隔离：程序和Codex拥有同一用户文件权限。Skill指令也不是强制ACL。若要求连宿主模型/恶意插件都不能读取隐藏文件，需要独立服务账户/远端裁判、认证的角色工具和独立无历史LLM会话。本交付没有实现这种部署，不能宣称绝对防作弊。未来LLM接入应取代worker内部策略，用独立请求、只发送AI View，绝不能接入当前主聊天历史；API凭证与费用需另行配置。

## 持久性与随机

Game State信封保存session_id、game_type、game_version、ruleset_version、revision、current_player、game_state、public_state、private_knowledge、turn_state、randomness_state及mode。实体牌有唯一ID；每次合法动作验证全牌守恒，旧ruleset不能用不同模块运行。

SQLite保存每桌活跃会话、完整状态、消息去重结果及修订快照。BEGIN IMMEDIATE锁定整个“读状态→人类动作→Null自动动作→存档”事务，WAL+FULL保证原子提交。失败动作在deepcopy上执行并回滚；seed和RNG计数也不变。存档文件权限0600；默认位置适用于当前Mac环境，跨多条消息和进程保存。保留会话无需常驻服务。跨聊天需使用同一table；相同cwd的默认table会共用，所以优先显式chat-ID。

正式随机种子来自secrets。HMAC-SHA256计数随机源用拒绝采样获得无偏范围，Fisher–Yates洗牌；随机偷牌、随机插回都使用同一私有程序源。种子、计数、随机审计只存在Game State。DEBUG可用任意字符串seed哈希为可复现种子。SQLite保存当前位置，使重启继续而不重新洗牌。nonce由程序secrets产生。

印加在输出“等你选择”之前，Null动作写入commitment（choice、nonce、sha256）。人类动作不能修改已存承诺。公开SHA256对应UTF-8串：

```text
session_id:round:decision_number:choice:nonce
```

揭晓后输出choice/nonce等校验数据。`reveal_history`保留所有已揭晓证明，`last_reveal`保留最近人机同步证明，Null独行不会覆盖它。哈希证明动作先锁定，不证明宿主防篡改；本地文件不是不可变账本。

## 增加游戏

在`scripts/duo/`增加模块，提供固定VERSION、setup(s)、legal(s,player)、act(s,player,action)、public(s)、extra_view(s,player)、zones(s)、expected(s)。在engine.MODULES注册模块。legal只能依据自己手牌和公开规则生成选项，不允许通过选项推断对方暗牌（比如仅当对方有拆弹才提供索要拆弹）。public及extra_view禁止跨角色输出隐藏数据；投影仍由engine统一构建。

为新模块增添language解析、render展示和ai_player策略，以及隐藏状态非干扰测试、非法动作不变测试、所有牌效边界和完整终局模拟。游戏特有阶段由turn_state表示；同步游戏要先承诺再接收人类动作，不能拿到用户文本后再pump补做AI选择。不要复制另一个Game State存储层或另建独立Skill。

## 测试范围

单元/行为测试涵盖三个规则模块、信息投影、真实worker边界、存档恢复、消息去重、防覆盖、Debug关闭、负向自然语言、秘密选择证明及3/2/1完整模拟。独立前向验证另用自然语言和每步新CLI进程完整游玩。用于证明已验证场景，不等于所有规则组合的形式证明或用户真人验收。

## v2信息权限与自动QA

common.py定义异常与带visibility标签的事件/私人知识；visibility.py管理HOST_STATE到PLAYER_KNOWLEDGE/NULL_KNOWLEDGE的标签、过滤、视图白名单和旧结构迁移。外层主持状态与RNG是HOST_ONLY；玩家手牌、动作选项、合法观察分别带PLAYER_ONLY或NULL_ONLY标签；事件逐条标记，HOST_ONLY事件不被投影。engine.projection先校验状态，再按允许字段构造；render与worker入口再次核对角色、标签和事件来源。

qa.py验证实体牌身份/牌面值/各区守恒、阶段、当前玩家、待执行回合、pending_bomb、Nope计数和响应者、Favor角色、当前私人知识与实际手牌/牌序的一致性、秘密承诺哈希。qa.transition禁止普通组合、非结束牌或否决响应换人。牌堆和手牌数直接取列表长度，不维护第二份自然语言账本；若旧数据另带count缓存则也核对。

store.py的faults独立表冻结有校验错误的桌，原sessions快照与history不动。play.py对StateError只返回paused=true、view=null及“状态校验失败”，不渲染可疑状态。RuleError表示非法用户动作，事务回滚后允许重选。错误详情不打印隐藏牌或存档内容。显式新建替换可清除该桌冻结，原坏局仍保留；修复是单独开发动作，没有自动修复接口。

kittens.introduce把首次获得的新牌效果作为各自私有事件保存；Null首次获得牌的帮助信息为NULL_ONLY，人类看不到。普通摸牌公共事件只记录抽1张且未爆炸。转移牌身份仅向参与者各自发私有事件，两人都参与也不改为PUBLIC。新输出带output_contract=2；旧去重缓存不回放旧文本，也不重复执行动作，提示查看现状。

新增回归测试见tests/test_regression_v2.py，旧版实体规则边界保留在tests/test_games.py。前者包括实际worker隐藏信息非干扰、强制响应、Nope奇偶、当前牌序、损坏存档冻结、旧存档保留、随机遗物加入和只读规则咨询。
