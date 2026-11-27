# Deadlock 数值、技能与角色设计

资料核对于 2026-11-27。案例来自 2024 年 10 月至 2026 年 11 月的 Valve 邀请测试版本，具体机制和参数随版本标注。[Steam 商店](https://store.steampowered.com/app/1422450/Deadlock/) · [官方更新日志](https://forums.playdeadlock.com/forums/changelog.10/)

## 研究结论

- **局内强度有几条可独立调节的曲线。** 累计获得的 Souls 推进成长，可支配的 Souls 用来买装备。Boon 成长、技能加点和装备分类投入分别决定属性何时增长、技能何时获得关键效果、出装何时触发额外收益。2026 年 11 月的生命和 Mina 改动，展示了如何保留满成长或加点后的表现，同时调整之前的强度。[Boon 成长表](https://deadlock.wiki/Boon) · [2025 年商店重做](https://store.steampowered.com/news/app/1422450/view/524216645064852902) · [2026-11-26 更新](https://store.steampowered.com/news/app/1422450/view/680768104678032838)
- **技能强度取决于双方能做什么。** Apollo 改版定义了哪些攻击会触发追击、哪些人可以被追击，以及谁能看到触发提示。The Doorman 的传送门和行李车则涉及地形、敌方可见性、驱散与防御建筑。拆技能时，这些字段和伤害、冷却一样值得记录。[2026-11-26 更新](https://steamcommunity.com/app/1422450/announcements/) · [2026-04-10 更新](https://forums.playdeadlock.com/threads/04-10-2026-update.125825/) · [The Doorman 版本记录](https://deadlock.wiki/The_Doorman/Update_history)
- **英雄主题可以约束整套交互，测试版可以逐步验证它。** The Doorman 的铃、门、行李车和酒店场景都延续同一个职业身份。Hero Labs 公开说明了玩家如何参与早期原型反馈。Sinclair 从占位大招迭代到复制对手的大招，提供了一条可追踪的版本记录。[The Doorman 官方介绍](https://steamcommunity.com/games/1422450/announcements/detail/524226158154219995) · [Hero Labs 公告](https://forums.playdeadlock.com/threads/10-24-2024-update.40951/) · [Sinclair 上线公告](https://steamcommunity.com/games/1422450/announcements/detail/786541361952194833)

## 章节

| 章节 | 研究问题 | 案例 |
| --- | --- | --- |
| [01 数值与经济设计](01_数值与经济设计.md) | 基础值、成长、升级节点和地图经济怎样共同决定局内节奏？ | 生命曲线、Mina、商店重做、Unstable Rift |
| [02 技能设计](02_技能设计.md) | 怎样描述技能的触发、目标、空间、反制和升级差异？ | Apollo 的反击、The Doorman 的空间控制 |
| [03 角色设计与迭代](03_角色设计与迭代.md) | 角色身份怎样落实到技能？从实验英雄到常规匹配经过了哪些公开迭代？ | Hero Labs、Sinclair、角色美术与动画 |
| [04 资料与复核方法](04_资料与复核方法.md) | 怎样对照公告、配置、沙盒和对局样本，复核一个设计问题？ | 数据源索引、交互测试和版本比较模板 |

## 关键版本

| 时间 | 公开记录 | 适合追踪的问题 |
| --- | --- | --- |
| 2024-10-24 | [Hero Labs 公告](https://forums.playdeadlock.com/threads/10-24-2024-update.40951/) | 原型测试允许哪些临时资源，玩家反馈何时介入 |
| 2025-01-17 | [四位英雄进入常规匹配](https://forums.playdeadlock.com/threads/01-17-2025-update.53607/) | 实验批次到常规玩法的过渡 |
| 2025-05-08 | [商店重做](https://store.steampowered.com/news/app/1422450/view/524216645064852902) | 装备槽位、组件升级和分类消费奖励 |
| 2025-08-22 | [The Doorman 发布](https://steamcommunity.com/games/1422450/announcements/detail/524226158154219995) | 角色身份与技能组的对应关系 |
| 2026-09-16 | [Unstable Rift 逆风参数调整](https://forums.playdeadlock.com/threads/09-16-2026-update.162572/) | 按比赛时间变化的增益上限 |
| 2026-09-29 | [City Never Sleeps](https://www.playdeadlock.com/cityneversleeps?pubDate=20260929) | 地图目标的风险收益、六位新英雄、沙盒测试工具 |
| 2026-11-26 | [数值与技能更新](https://store.steampowered.com/news/app/1422450/view/680768104678032838) | 生命成长、技能升级系数、反击触发规则 |

公开资料可以回答某一版本的规则、参数和已披露的改动原因。Valve 的完整策划案、内部强度预算、测试阈值与全量对局数据，在本次资料核对范围内仍缺少可核实的公开来源。各案例将公开事实与设计解读放在相应段落，对历史参数保留日期。
