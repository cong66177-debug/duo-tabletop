# duo-tabletop · 双人桌游陪玩

在聊天中与 AI 对手玩双人桌游，支持情书、爆炸猫和印加宝藏。通过自然语言出牌、抽牌、探险和撤退，由本地程序负责规则结算、状态记录与存档。

一个 Skill，三个游戏模块。适用于能够读取技能文件并执行本地 Python 脚本的 Codex 环境。

## 支持的游戏

| 游戏 | 当前采用的玩法 |
|---|---|
| 情书 / Love Letter | AEG 经典16张，双人局，先获得7枚好感标记获胜。 |
| 爆炸猫 / Exploding Kittens | 2017经典版，双方起手5张，支持两张、三张和五种不同牌组合；Attack使对方执行两个完整回合，该版反击不叠加。 |
| 印加宝藏 / Incan Gold | 五轮探险；遗物按牌面5、7、8、10、12分计分，每轮秘密加入一张，加入顺序随机。 |

印加采用明确的非官方双人适配，随机加入遗物为本项目采用的玩法安排；不宣称是官方双人规则。也可用“Diamant”名称触发该模块。旧版存档按原规则版本继续，不中途重算牌序或得分。

详细版本与规则来源见 [references/rulesets.md](references/rulesets.md)。

## 功能

- 自然语言操作，无需记住程序命令。
- 手牌以同名合并计数显示，爆炸猫使用emoji与简短牌效提示。
- 自动执行对手行动，维护当前玩家、回合阶段和Attack剩余回合。
- 可否决动作先进入Nope响应窗口，支持反否决。
- 双方分别保存通过规则合法获得的私人知识。
- 印加同时选择采用持久化的秘密决定与commit/reveal。
- SQLite持久存档，可以恢复同一桌的对局。
- 每步检查牌数、实体牌、阶段和信息权限；校验失败暂停该桌并保留原存档。
- AI对手带有简短角色台词，台词在规则与信息检查通过后生成。

## 环境要求

- 本地 **Python 3.8或以上**，包含标准库 `sqlite3`。
- Codex具有执行本地脚本及读写对局存档目录的权限。
- 使用Git克隆安装时需要Git；下载ZIP安装时不需要Git。

游戏引擎只使用Python标准库，**无需执行 `pip install`，也不需要额外配置API密钥**。聊天宿主本身所需的账号或订阅另行准备。

可以在终端检查环境：

```bash
python3 --version
python3 -c "import sqlite3; print('SQLite available')"
```

普通不提供本地脚本执行工具的ChatGPT网页聊天，无法仅靠粘贴 `SKILL.md` 运行这套引擎。当前主要在macOS本地环境完成验证。

## 安装

### 方法一：下载ZIP

1. 在本仓库点击 **Code → Download ZIP**，解压文件。
2. 将包含 `SKILL.md`、`scripts/`、`references/` 等内容的目录改名为 `duo-tabletop`。
3. 将整个目录放到用户技能目录 `~/.agents/skills/` 中。目录不存在时自行创建。
4. 确认文件位置是 `~/.agents/skills/duo-tabletop/SKILL.md`，不要多套一层文件夹。

安装后的结构：

```text
~/.agents/skills/duo-tabletop/
├── README.md
├── SKILL.md
├── agents/
├── scripts/
├── references/
└── tests/
```

### 方法二：使用Git

将下面的 `YOUR_USERNAME` 替换为本仓库所属的GitHub用户名；如果仓库名不同，也修改仓库名：

git clone https://github.com/cong66177-debug/duo-tabletop.git ~/.agents/skills/duo-tabletop

如果已有同名技能，更新原安装目录，不再创建第二份同名安装。

Codex通常会自动检测技能；若没有出现，重启Codex后再试。用户技能目录及自动检测行为参见 [OpenAI官方技能文档](https://learn.chatgpt.com/docs/build-skills)。

## 开始游玩

安装后，在Codex聊天中输入：

```text
使用 $duo-tabletop，来玩桌游。
```

或直接指定游戏：

```text
来一局情书
来一局炸弹猫
我们去探险
```

对局中可以这样说：

```text
我出侍女
猜你是王子
两张彩虹猫偷你的牌
直接抽牌
否决
过
攻击怎么用
继续深入
返回营地
下一轮
恢复游戏
```

系统会根据当前阶段提示可执行动作。出组合不会自动结束爆炸猫回合；需要继续出牌、抽牌，或使用能结束回合的牌。

## 存档与恢复

默认存档位置是：

```text
~/Documents/Codex/duo-tabletop-data/
```

在同一聊天中说“恢复游戏”可继续原对局。跨聊天恢复需要沿用原桌号；仅在另一段聊天里说“恢复游戏”，不保证自动识别之前的桌。

存档保存在本地，不会自动上传到GitHub。开发测试可通过 `--data-dir` 使用单独目录。

## AI对手与公平边界

对手由独立的程序策略进程运行，只接收自己的手牌、公共信息及通过合法牌效获得的私人知识。聊天模型处理玩家意图并展示经过过滤的玩家视图，不能代替对手决定动作。

因此，本项目的AI对手采用程序策略，而非第二个独立聊天模型。数据投影可以隔离正常决策流程，但本地文件权限并非操作系统级的强制防作弊隔离。

同时选择使用真实SHA256与持久化承诺；本地存档仍不是防篡改账本。更强的隔离需要独立裁判服务、角色鉴权或独立系统账户。

## 项目结构

```text
SKILL.md                  技能入口与玩法约定
agents/                   技能界面元数据
scripts/play.py           聊天与命令行入口
scripts/ai_player.py       独立对手策略
scripts/duo/              游戏规则、状态、权限、QA和展示模块
references/               规则来源、动作协议与架构说明
tests/                    单元测试与试玩问题回归测试
```

## 运行测试

在仓库目录中执行：

```bash
python3 -m unittest discover -s tests -v
```

当前版本已通过80项自动测试，包含三款游戏的完整终局模拟，并完成独立自然语言试玩。测试覆盖Guard决策非干扰、隐藏摸牌、私人知识更新、Attack两个回合、Nope链、组合、同时决策、单人继续探险、牌数守恒及损坏存档暂停等场景。

