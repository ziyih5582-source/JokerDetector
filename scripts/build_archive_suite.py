"""Authored continuous cases plus a separately attributed public research slice."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def step(text, day="2026-10-07", expected=(), forbidden=(), empty=False, resolve=None):
    return {"text": text, "day": day, "expected": list(expected), "forbidden": list(forbidden),
            "empty": empty, "resolve": resolve}


def long_chat(core, place="middle", size=90):
    topics = ["课程阅读", "食堂排队", "校车路线", "图书馆座位", "讲座笔记", "打印机排队", "社团海报",
              "校园展览", "运动场开放", "小组教室", "散步路线", "课件格式", "校园地图", "讲义页码",
              "课程例题", "储物柜编号", "自习室灯光", "食堂菜品", "校内书店", "公交站牌", "教室窗帘",
              "楼梯指示牌", "舞台背景", "湖边步道", "选修课教室", "实验材料", "校园纪念册"]
    rows = []
    for i in range(size):
        topic = topics[i % len(topics)]
        rows += [f"我：刚看到群里第{i+1}条关于{topic}的消息，里面那张图左边有两种说明。我只是在核对这次通知的意思，你看到的是一样的吗？",
                 f"TA：第{i+1}条通知我也看到了，截图中浅色那部分应该只是示意。我把原文里的两处标注重新看了一下，它们分别讲位置和说明，按原文核对就行。这段只是在核对通知，没有额外约定。"]
    offset = 0 if place == "start" else len(rows) if place == "end" else len(rows)//2
    rows[offset:offset] = core.splitlines()
    return "\n".join(rows)


def authored():
    cases = []
    def add(cid, scene, steps, tags=None):
        cases.append({"id": cid, "name": cid+" · 研究样例", "scene": scene, "tags": tags or [],
                      "source": "authored_synthetic", "steps": steps})
    add("S01", "暧昧了解", [step("我：晚上要聊会儿吗？\nTA：我喜欢慢慢熟悉，刚认识时别每天追问我在干嘛。", expected=["刚认识|慢慢熟悉", "追问|每天"]),
                            step("我：那聊游戏？\nTA：好呀，我喜欢星露谷慢慢种地，不喜欢一上来催我冲进度。", expected=["星露谷", "催|进度"])], ["crush"])
    add("S02", "日常倾诉", [step("我：这次实验报告怎么了？\nTA：心里有点堵，今天只想说说，不用马上给我解决办法。", expected=["今天|这次", "说说|倾诉|解决办法"])])
    add("S03", "兴趣观点", [step("我：喜欢哪种篮球玩法？\nTA：我爱半场传切，大家轮流有球打才有意思，不喜欢一人一直单打。", expected=["传切", "单打|轮流"])])
    add("S04", "与长者沟通", [step("我：叔叔，我先问您在不在？\nTA：不用特意问在不在，事情和你想确认的地方一起发文字就行。", expected=["文字", "在不在|一起"])], ["长者"])
    add("S05", "任务节点", [step("我：分享会用哪个版本？\nTA：今年10月16日下午交文字提纲， slides 还不用交。", expected=["提纲", "10月16|2026-10-16"]),
                             step("我：提纲还按16日？\nTA：提纲现在改到今年10月18日下午，仍然只是文字提纲。", day="2026-10-08", expected=["提纲", "18|2026-10-18"])])
    add("S06", "作品看法", [step("我：你说喜欢那个角色，是为什么？\nTA：我喜欢《排球少年》里普通人坚持练习的部分，不是只喜欢赢比赛的剧情。", expected=["排球少年", "坚持|普通人"])])
    add("S07", "明示关系", [step("我：你刚刚在看小说？\nTA：小说只是让我想起这事。说我自己：我想继续了解你，但目前还不想确定恋爱关系。", expected=["了解", "不想确定|还不想|未确定"])], ["crush"])
    add("N10", "台词转述", [step("我：你刚说啥？\nTA：室友在念小说里的‘我喜欢你’，我是在解释她念的那一句。", forbidden=["TYPE:relationship_position"])])
    add("N11", "普通寒暄", [step("我：借的笔还你，谢谢！\nTA：嗯嗯，不客气，明天见。", empty=True)])
    add("N12", "假设", [step("我：假如有人愿意一起看电影就是喜欢？\nTA：如果我愿意看电影，也可能只是想看电影啊，这只是讨论假设。", forbidden=["TYPE:relationship_position"])])
    add("N13", "双方归属", [step("我：我最喜欢打排位。\nTA：我不打排位，只想休闲模式放松一下。", expected=["休闲", "不打排位|不.*排位"], forbidden=["对方喜欢.*排位|双方都.*排位"])])
    add("N14", "拒绝并友好", [step("我：你会分享日常，是不是愿意发展恋爱？\nTA：我只想和你做朋友，分享是因为把你当朋友，不是在暗示恋爱。", expected=["朋友"], forbidden=["对方愿意发展恋爱|欲擒故纵"])], ["crush"])
    add("N15", "无信息片段", [step("我：嗯。\nTA：嗯嗯。", empty=True)])
    add("M01", "边界变化", [step("我：照片可以发群里吗？\nTA：可以发我这张照片，但别加情侣梗。", day="2026-10-01", expected=["情侣|照片"]),
                             step("我：昨天那张也可以？\nTA：现在我不想让照片出现在群里，之前那张也请撤掉。", expected=["照片|撤掉"], resolve="accept")], ["crush"])
    add("M02", "兴趣细化", [step("我：休息时喜欢做什么？\nTA：我会玩星露谷，主要享受慢慢种田，不赶进度。", day="2026-10-01", expected=["星露谷", "种田|进度"]),
                             step("我：星露谷联机怎么玩舒服？\nTA：我喜欢各自做事，有空再碰头，不用全程语音连着。", expected=["语音", "各自|碰头"])])
    add("M03", "迟到旧资料", [step("我：最近更想怎么相处？\nTA：我现在愿意和你约会了解，但我们还没有正式在一起。", day="2026-10-07", expected=["约会", "没有.*在一起|未.*确定"]),
                             step("我：先前怎么想？\nTA：我现在只想和你做朋友。", day="2026-09-20", expected=["朋友"])], ["crush"])
    add("M04", "阶段需要变化", [step("我：作业很多，我帮你安排？\nTA：今天先听我吐槽吧，我只是累了，暂时不想安排计划。", day="2026-10-01", expected=["吐槽", "今天|暂时"]),
                                 step("我：今天想继续说还是列计划？\nTA：今天已经缓过来了，想把报告拆开做，先列个提纲吧。", expected=["提纲|拆开", "今天"])])
    style = "我：刚才群里你没怎么说话。\nTA：群里都是不认识的人，话题跳得快，我插不上话。"
    hobby = "我：你怎么把游戏剧情讲得这么细？\nTA：和你私聊自己熟悉的东西我就很愿意讲，昨天聊番剧也是，聊到观点可以慢慢说。"
    repair = "我：所以你是不喜欢群聊吗？\nTA：不是，我在熟人群也会很能聊。陌生人多且话题跳得快时才难插话，跟是不是私聊不是一回事。"
    for cid, placement, size in [("L10", "start", 75), ("L11", "middle", 100), ("L12", "end", 150)]:
        add(cid, "长篇连续相处", [step(long_chat(style, placement, size), day="2026-10-01", expected=["不认识|陌生", "话题|插.*话"]),
                                   step(long_chat(hobby, placement, size), day="2026-10-04", expected=["私聊|熟悉", "观点|番剧"]),
                                   step(long_chat(repair, placement, size), expected=["熟人|陌生", "话题|插.*话"], resolve="accept")], ["crush"])
    add("L13", "长篇混合", [step(long_chat("我：我们一起联机怎么样，截图可以随便发吗？\nTA：可以一起玩，但别把我吐槽的截图发群里。我喜欢自己探索地图，别提前说谜题答案。\n我：那今晚去？\nTA：今天在赶实验报告，这周五结束前不方便，结束后再约时间。", "middle", 130), expected=["截图", "答案|剧透|探索", "报告|这周五"])])
    add("O01", "从行为形成有限认识", [step("我：群里刚聊那段剧情，你怎么看？\nTA：群里我只回了个表情。这里我想详细说：那个角色做的选择让我想了很多，他没有立刻替朋友做决定，而是先问朋友想要什么。\n我：你可以接着说。\nTA：我还想到另一段，我们私下慢慢聊这个吧，我想把两处区别讲清楚。", expected=["私下|私聊|详细|慢慢"]),
                                      step("我：你昨天私聊说得多，是因为不喜欢群聊吗？\nTA：不是不喜欢群聊，昨天我刚好有空，群里的消息刷太快。和熟人群聊我也会讲很多，不能说我一贯只爱私聊。", expected=["熟人|消息|有空"], resolve="accept")])
    add("O02", "可观察的表达差异", [step("我：[群聊片段]那部作品大家怎么看？\nTA：[群聊片段]嗯，还行。\n我：[私聊片段]你想聊聊你自己的看法吗？\nTA：[私聊片段]我想到角色最后没有替朋友决定那段，觉得很有意思。我还记得前面有一个呼应，一开始他总觉得自己帮人解决问题就是对的，后来才学会听。\n我：[私聊片段]我没有注意到前面的呼应。\nTA：[私聊片段]我再说具体一点，前面他抢着给答案，后面先问朋友想做什么。我想聊的是这两处区别。\n我：[群聊片段]另一个话题你要接着说吗？\nTA：[群聊片段]你们先说。", expected=["私聊|具体|看法|观点"], forbidden=["对方肯定喜欢|天生.*内向"])])
    rich1 = """我：今天课终于结束了，路上你说起那个电影，我没听完整。
TA：我喜欢它没有把两个人立刻写成圆满结局。比起最后有没有在一起，我更在意他们愿不愿意认真听对方把话说完。
我：我刚才只顾着讲自己的解读，可能抢了你的话。
TA：这次倒还好，我停下来是在想怎么解释。以后如果我说‘等我讲完’，就是还想继续说，不用替我收尾。
我：那就接着聊，片里回到校园那段你怎么看？
TA：我觉得那个地方像真实生活，大家并不是每天都能给完美回应。有时候先说自己没空，也比装作认真听要好。
我：现实里每天问候会让你觉得舒服吗？
TA：刚认识时别每天查我在哪、跟谁一起吧。我愿意分享，但想自己决定分享多少。
我：了解，我不把你分享的事拿去群里讲。
TA：对，尤其别把我吐槽课程的截图转群里。这些话只是私下说说，不是要公开评价谁。
我：上次你展示讲得不错，你自己感觉怎样？
TA：第一次上台能把内容讲完整，我已经很开心了。今晚想庆祝一下，不想马上把所有口误再复盘一遍。
我：我以为马上提意见就会有帮助。
TA：下次可以先问我想听感受还是修改建议。我想改的时候会说，但庆祝时更想有人一起开心。
我：你周末休息会玩什么？
TA：星露谷吧，慢慢种地挺放松的。我不想为了所谓效率把休息也弄成赶任务。
我：我联机总喜欢抢着安排路线，看来不太合适。
TA：可以各自做事，碰到好玩的再分享，不用全程语音连着。一起玩不代表每个步骤都要同步。
我：同一个游戏原来也可以玩得很不同。
TA：对，我不反对你想冲进度，只是不想被要求同一种玩法。有交集已经挺好，没必要所有偏好一样。
我：你上次说那个音乐演出怎么样？
TA：现场的合唱那段让我觉得大家都在参与，比只盯着舞台主角更有意思。这是我当时的感受，不是所有演出都得那样。
我：今晚还想一起去买点吃的庆祝吗？
TA：可以，去书店旁边那家小店吧。只是一起庆祝展示结束，别叫成约会，我现在还是想慢慢了解。"""
    rich2 = """我：今天报告还有很多吗？
TA：实验数据核对挺烦的，今天先让我吐槽完，暂时别帮我排计划。我知道你想帮忙，但我现在只想有人听。
我：好，我先听。最麻烦是哪一部分？
TA：是不同记录表对应不上，来回找原始记录有点累。吐槽完我可能自己就能继续做，明天再谈具体修改也行。
我：你前两天分享游戏地图，我后来也去探索了。
TA：那张地图我还没走完，先别告诉我谜题答案。我喜欢自己发现入口，卡住了会主动问。
我：我之前发过一个攻略，可能已经算剧透。
TA：你当时问过我能不能发，我同意的是开头那一段，不是全部路线。以后我们先说清楚范围就好。
我：群里大家问你怎么不参加聚餐，我可以帮你解释？
TA：不用替我解释成不喜欢大家，我这周报告没做完。周五结束之前都不方便，之后我会自己说什么时候能去。
我：那我不替你回答，下周再看。
TA：谢谢。也别说成我永远不爱热闹，熟人的活动我有时也想参加，只是这几天忙。
我：刚刚聊到电影里的那个选择，我想起你的看法。
TA：还是那个意思，先问当事人想怎样，比急着给一个看似正确的答案更重要。不过现实里如果别人已经明确请求建议，就可以直接讨论方案。
我：我之前理解成你完全不想要建议。
TA：不是，今天只想吐槽和永远不接受建议差很多。需要什么可以随当天情况再确认，不用把一次状态当习惯。
我：上次庆祝我没有马上提口误，你觉得怎样？
TA：那次能先一起开心挺好的。后来我自己想改讲稿时才找你看，那个时候的意见就有帮助。
我：所以听完以后可以问是否想一起想办法？
TA：可以先问一句，我愿意就会说。不用每次重复一大段安慰套话，自然接着聊就行。
我：周末书店的新活动，你会考虑吗？
TA：等报告结束再看，先不要替我报名。我不想让没确定的安排变成一个已经答应的事情。
我：那等你主动确认，我们再商量。
TA：好，时间地点确认后发文字给我，这几天图书馆里不方便听长语音。"""
    rich3 = """我：报告交了，周末的书店活动要继续约吗？
TA：报告现在已经交完了，可以看看活动。周日下午比较空，周六我还要排练，这两个安排别弄反。
我：约的时候我把时间地点一条发清楚。
TA：对，还有是不是要报名也一起写吧。临时改时间的话先跟我确认，不用替我跟其他人承诺。
我：你把整个游戏地图都探索完了？
TA：对，现在地图的谜题我都做完了，那部分可以聊答案。不过新出的后续章节我没玩，那个还是先别剧透。
我：所以旧地图可以讨论，新章节仍然保留。
TA：嗯，范围不同。以前别剧透不是永远禁止说这个作品，我想自己先体验的部分才需要留着。
我：你在排练群里比我们刚认识时健谈很多。
TA：那里都是熟人，大家话题也熟。陌生人很多而且话题跳得快时我才不知道怎么插话，跟私聊还是群聊不是一回事。
我：那之前我把你理解成只爱私聊，太宽了。
TA：可以这么修正。我和你聊熟悉东西时愿意讲，也会在熟人群讲，不用把我定成一直慢热的人。
我：周日一起逛书店算不算约会？
TA：现在我愿意把这次当作约会来了解你，但还没有正式在一起。群里先别替我们宣布，等我们自己确定再说。
我：我记得你之前说慢慢了解，那现在多了一步。
TA：对，我们的相处有变化，但不代表所有边界都消失了，私下聊天截图和公开起哄仍然是我不想要的。
我：要是聊到展示的不足，今天能讨论吗？
TA：今天可以，我想改一下开头那段。和当天庆祝时不同，现在我主动想听修改意见。
我：那我先指出两处，再听你的想法。
TA：好，先说具体哪句话、为什么不清楚。只说‘你表达能力差’会让我不知道怎么改，具体例子才有帮助。
我：你想继续玩星露谷还是试新游戏？
TA：星露谷的慢节奏还是喜欢，新游戏也可以试，但不用因为我喜欢种田就判断我所有竞技游戏都不碰。
我：那以后聊到新的，就看具体玩法。
TA：对，某个游戏里想放松只是那个游戏的偏好，别扩成我生活中什么竞争都回避。"""
    add("L20", "信息丰富的连续长聊", [step(rich1,day="2026-10-01",expected=["截图", "星露谷", "慢慢了解"]),
                                       step(rich2,day="2026-10-04",expected=["剧透|答案", "吐槽|建议", "报告"]),
                                       step(rich3,expected=["约会", "新.*章节|后续", "熟人|陌生"],resolve="accept")], ["crush"])
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", type=Path)
    args = parser.parse_args()
    original = json.loads((ROOT/"backend/tests/fixtures/campus_cases.json").read_text(encoding="utf-8"))
    for c in original:
        c["source"] = "previous_authored_synthetic"
        for s in c["steps"]:
            s["expected"] = []
            s["forbidden"] = ["TYPE:"+k for k in s.get("forbidden_types", [])] + s.get("forbidden", [])
    cases = original + authored()
    if args.public:
        public = [json.loads(s) for s in args.public.read_text(encoding="utf-8").splitlines() if s.strip()]
        selected = []
        for row in public:
            text = row["dialogue"]
            if len(text)<250 or len(text)>2400 or any(w in text.lower() for w in ("doctor", "medical", "salary", "religion", "president", "#person3#")):
                continue
            if not any(w in text.lower() for w in ("friend", "class", "music", "game", "book", "meeting", "college", "teacher")):
                continue
            text = text.replace("#Person1#", "我").replace("#Person2#", "TA")
            lines = []
            for line in text.splitlines():
                who, content = line.split(":", 1)
                lines.append(who+"："+content.strip())
            selected.append({"id":"P"+str(len(selected)+1).zfill(2),"name":"公开研究对话 "+row["fname"],
                             "scene":"公开语料，具体关系未知", "tags":[], "source":"DialogSum public research corpus",
                             "source_id":row["fname"], "license":"CC BY-NC-SA 4.0",
                             "source_url":"https://github.com/cylnlp/dialogsum", "steps":[step("\n".join(lines))]})
            if len(selected)==8:
                break
        cases += selected
    target = ROOT/"backend/tests/fixtures/archive_suite.json"
    target.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    steps = [s for c in cases for s in c["steps"]]
    lengths = [len(s["text"]) for s in steps]
    print(json.dumps({"groups":len(cases),"uploads":len(steps),"short_under_500":sum(n<500 for n in lengths),
                      "long_over_10000":sum(n>10000 for n in lengths),"max_chars":max(lengths),
                      "public_groups":sum(c["id"].startswith('P') for c in cases)},ensure_ascii=False))


if __name__ == "__main__":
    main()
