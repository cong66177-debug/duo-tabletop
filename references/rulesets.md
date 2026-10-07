# 固定规则及核准来源

核准日期：2026-10-07。程序VERSION固定；同名新印次不得直接替换现有规则。没有牌面图片、未复制完整出版物，以下为实现选择及差异记录。

## 情书

`love-letter-aeg-classic16-2016-2p-v1`：依据AEG Premium官方规则书的**2–4人基础16张部分**（不是32张扩展玩法）。Guard1×5；Priest2/Baron3/Handmaid4/Prince5各×2；King6/Countess7/Princess8各×1。双人暗置1、公开移除3、双方各1，轮到时摸1出1。牌效强制，侍女防对方选中至下回合开始；王子可选自己且对方全保护时必须选自己；公主因任何原因弃掉均淘汰且不重抽；王子在空牌堆时使用暗置牌。牌堆耗尽在完成当回合牌效后结算，先比手牌，再比弃牌总值，仍同分共享好感。完整场先到7好感；轮间需“下一轮”。开局人类先手；原规则约会先手无法自动确定，轮间平手先手改为程序随机，明确属于聊天便利适配。

牧师、男爵及交换产生的合法私人观察单独保存。对方摸牌形成两张手牌后，旧观察立即降为历史不确定；王子/国王/出局也使旧确定性失效。历史资料不被抹掉；不宣称它还是对方当前手牌。

[AEG官方规则PDF](https://alderac.com/wp-content/uploads/2017/11/Love-Letter-Premium_Rulebook.pdf)，核对页4–6、8–10。
SHA256：`c6ed5920ff051ef266a6e7c208548f8739abf3d822afdf11d0530fdd8a3d827b`。

## 爆炸猫

`exploding-kittens-original-2017-special-combos-2p-v1`：固定**Copyright 2017 Original Edition**出版商规则书。当前2022 PDF修改了发牌/Attack并省去五不同组合，故没有采用它的规则。56张：Exploding Kitten4、Defuse6、Nope5、See the Future5、Attack/Skip/Favor/Shuffle各4、五种Cat各4。

2017双人开局**4张随机牌+1拆弹=5张**；牌堆回放2张额外拆弹和1张炸弹；移除余下2拆弹与3炸弹，初始牌堆41张。与需求中的8张手牌显示例子无冲突：那只是显示格式，之后手牌可增加。

Attack立即结束自己全部待执行回合，对手获得2个完整回合；本版本反击仍是2，**不叠加4/6**。Skip或一次抽牌只结束1个待执行回合；拆弹后秘密插回也结束1个回合。普通牌可在抽牌前连出。See the Future只看前三，洗牌后原顺序失效。Favor由被索要者选牌。无拆弹抽到炸弹则弃全部牌出局。

启用三组经典Special Combos：同名2张随机偷、同名3张指定牌名、5种不同牌名从公开弃牌取1。猫牌和功能牌均可作材料，忽略牌效。Nope可取消组合及Nope，不能取消抽牌、爆炸或拆弹。所有可否决动作先放牌、轮流回应；两次连续pass才执行，Nope重置pass计数。为聊天离散回合设置的公平窗口取代实体桌面“尽快拿起弃牌堆”竞速；五张组合的取回牌在出组合时指定，响应窗口结束后取回，包括该次已投入弃牌堆的材料。没有扩展包牌。

[出版商2017规则书镜像PDF](https://cdn.1j1ju.com/medias/e7/ec/08-exploding-kittens-rules.pdf)（文档作者Exploding Kittens，镜像域名不是官方域名），核对两页。
SHA256：`09c5cd1cc82cb1e9b17db1d23a7f398a259487151824b3baad8f93ee2487072c`。
[当前官方说明书入口](https://www.explodingkittens.com/pages/rules-kittens/thanks)、[2022官方PDF](https://dumekj556jp75.cloudfront.net/exploding-kittens/English.pdf)仅用于版本差异核对，未混入实现。

## 印加宝藏

`incan-gold-egg-2018-numbered-artifacts-2p-adaptation-v1`：采用Eagle-Gryphon **©2018、meeple、编号遗物**规则。正式人数3–8；这里只把参与人数改为2，不加虚拟第三人，其余分配/危险/遗物/轮数保持该版。**这是非官方双人适配，不能宣称官方双人规则**，也不是另一个Diamant版本。

15宝石牌值：1、2、3、4、5、5、7、7、9、11、11、13、14、15、17；五类危险（蜘蛛、木乃伊、火、蛇、落石）各3；5遗物值5、7、8、10、12，按轮加入。每轮重洗未永久移除的牌；没翻出的旧遗物留在后续牌堆。宝石在仍探索的人之间整除，余数留路径；返回者先分路径余数，再带回自己的本轮财富。唯一返回者取全部路径遗物，两人同回无人取。返回处理在下次翻牌前，因此撤退者不受下一张灾难影响。第二张同类危险使在场者未带回财富归零，移除第二张危险；轮末路径上未带走遗物永久移除。帐篷财富不由程序给对方查看（公共历史可以自行记账）。五轮后宝石加遗物计分，同分比遗物件数。

[发行商2018产品和规则入口](https://www.eagle-gryphon.com/products/incan-gold-2018) → [官方公开规则目录](https://drive.google.com/drive/folders/1lEcFycJEAlqFo681sFb4hCQ4bnZeV-UQ) → [Incan Gold Rulebook.pdf](https://drive.google.com/file/d/1dUqSh-rCYACXEGvL4Hn-wKSthLfwzzks/view)，本次实际下载并核对4页。
SHA256：`50d0f6a1142ee5232457fcb94a4648acd6e6bcb8246274ed96b9a2e93607bdae`。

证据细分：2018官方PDF确认15张宝石及全部处理机制，但未逐张列值。数值列表另与[原作Schmidt出版规则书镜像第1页](https://www.jeuxavolonte.asso.fr/regles/diamant.pdf)逐项核对；该原作的其他危险名/计分/帐篷规则没有导入。设计师[2018版本说明](https://faidutti.com/blog/blog/category/principaux-succes-main-hits/page/2/)确认当年更新美术、编号遗物规则及meeple。采用原作相同宝石分布属于据这些来源作出的版本连续性推断，未获得2018实物逐牌表直接证明；需将此证据限制与已直接核准的规则分开说明。授权BGA旧索引也列相同15值，但当前可编辑帮助页错误地列14张，未以该页作为实现依据。

没有采用旧版“最先取出三件各5分、后来各10分”（用户最新确认仍按编号牌面分值），也没有采用2024新美术的其他危险名称。首张默认双方进入（规则允许跳过初次无财富选择）；之后每次秘密决定，程序承诺先于用户输入。

## 当前默认印加v2与旧存档

用户于2026-10-07确认：遗物分数取牌面5、7、8、10、12，随机决定每轮加入哪张。新局使用`incan-gold-numbered-artifacts-random-entry-2p-v2`：开局程序秘密洗混五件遗物，逐轮加入一张；未翻出前不公开该件分值，翻出后公开；唯一撤退者获取并按该牌值计分。不使用“最先带回三件固定5分”。随机加入与双人人数均作为明确的用户玩法适配记录，不声称新增安排是原2018说明书规定。

旧`incan-gold-egg-2018-numbered-artifacts-2p-adaptation-v1`会话仍按原5/7/8/10/12顺序加入，按ruleset_version分支读取；不重新洗旧future_artifacts、不重算旧得分、不改已保存的秘密决定。schema1→2只增加信息标签，不改变牌、随机源或规则版本。
