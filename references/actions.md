# 人类动作协议

正常优先使用`chat --text`原话；以下只用于解析未覆盖且明确的表达。全局参数先于子命令；`--action`是单个JSON参数。入口总是human角色，无对手动作接口。`--json`返回Human View（可能包含许多合法选项），不返回Game State。

| 游戏/阶段 | 动作JSON示例 |
|---|---|
| 情书出牌 | `{"type":"play","card":"Handmaid"}` |
| 情书卫兵 | `{"type":"play","card":"Guard","target":"ai","guess":"Prince"}` |
| 情书牧师/男爵/国王 | `{"type":"play","card":"Priest","target":"ai"}` |
| 对方侍女保护时上述四牌 | `{"type":"play","card":"Guard","target":null}`（无牌效） |
| 王子自选 | `{"type":"play","card":"Prince","target":"human"}` |
| 爆炸猫出功能牌 | `{"type":"play","card":"Attack"}` |
| 两张同名组合 | `{"type":"combo2","cards":["Attack","Attack"]}` |
| 三张同名索要 | `{"type":"combo3","cards":["Taco Cat","Taco Cat","Taco Cat"],"request":"Defuse"}` |
| 五张不同取回 | `{"type":"combo5","cards":["Attack","Skip","Favor","Shuffle","Taco Cat"],"retrieve":"Defuse"}` |
| 否决/过 | `{"type":"nope"}` / `{"type":"pass"}` |
| 抽牌 | `{"type":"draw"}` |
| 被Favor要求交牌 | `{"type":"give","card":"Taco Cat"}` |
| 秘密插回 | `{"type":"insert","position":0}`（程序0基，上方第一张；允许0..deck_count） |
| 探险继续/返回 | `{"type":"continue"}` / `{"type":"return"}` |
| 情书/探险下一轮 | `{"type":"next_round"}` |

普通猫牌名：`Taco Cat`、`Cattermelon`、`Hairy Potato Cat`、`Beard Cat`、`Rainbow-Ralphing Cat`。其他爆炸猫牌名：`Defuse`、`Attack`、`Skip`、`Favor`、`Shuffle`、`See the Future`、`Nope`、`Exploding Kitten`。功能牌不能拿两张当两个连续动作；同时出的匹配牌是Special Combo。Defuse只在抽到炸弹时生效，也可作为组合材料；Nope只有响应窗口能单张出。情书Guard猜牌不能猜Guard。

返回`ok=false`时动作未提交，展示error并请用户重选，不静默执行候补动作。复合自然语言拆成单个动作需要用户明确授权序列，不能越过中间响应/秘密选择阶段。

牌名支持“炸弹猫”“毛茸茸猫”“彩虹猫”等中文别名。爆炸猫询问“某牌怎么用/效果/作用”返回效果和你现有张数，revision与牌账不变；“如果...”讨论不会提交动作。返回paused=true表示校验失败并冻结本桌，不能当作普通非法动作继续。
