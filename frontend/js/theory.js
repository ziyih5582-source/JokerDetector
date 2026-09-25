/**
 * 心理学依据 · 交心 · 思源湖研究所
 *
 * 改内容只需要动这个文件。
 *   window.THEORY = { intro, groups: [{ mark, title, note, items: [item] }], caveats: [...] }
 * item 字段：
 *   name 中文名 / en 英文名 / who 提出者 / year 年份
 *   core 核心主张 / evidence 关键实证（含证据强度）/ caveat 注意点
 *   inapp 在本项目里对应什么 / ask 「去和钓翁聊聊」的预填问题 / sources [{label,url}]
 *
 * 写作约定（重要）：
 *   只写有出处的内容。凡是「未能核实」的数字（百分比、效应量、样本量）一律不写，
 *   改成定性表述；年份若无法核实则标注「常见引用」。宁可少写，不许编。
 *   资料核实稿（含逐条 DOI 与未能核实清单）保存在 .dsh-tools/research/，未入库。
 */
window.THEORY = {
  intro: '这一页把项目里那些指标背后的心理学依据摊开来讲：每条都写明提出者、年份、可核查的出处，以及证据到底有多强。其中有几条是中文科普常写错、甚至已经被重复检验否定的——它们也被收了进来，只是标注得更清楚。',

  groups: [
    {
      mark: '一',
      title: '亲密关系的结构',
      note: '爱情由什么组成、又有哪些形态——这一类理论回答的是「它是什么」。',
      items: [
        {
          name: '爱情三角理论',
          en: 'Triangular Theory of Love',
          who: 'Robert J. Sternberg',
          year: '1986',
          core: '爱情由三个成分构成：亲密（理解与情感联结）、激情（吸引与强烈驱力）、承诺（维持关系的决定）。三个成分的不同组合构成不同类型的爱，三者兼备即「圆满之爱」。',
          evidence: '这是一篇理论建构论文（《Psychological Review》本身是理论刊物），贡献是成分模型与类型学，不是实验数据。由三个成分的组合可以推出八种爱：无爱、喜欢、迷恋、空爱、浪漫之爱、伴侣之爱、愚爱、圆满之爱——这是模型的结构性推论，不是实证发现。',
          caveat: '三个成分如何测量长期有争议：激情在长期关系中会衰减，承诺又很容易和「沉没成本」混淆。「圆满之爱」是理论上的理想组合，不是实证上最优的预测指标。',
          inapp: '五维里的「情感表达差」「对话衔接度」可以看作亲密成分的粗糙代理，「连续发送倾向」更像激情与焦虑的混合物。它们都不是对三成分的测量。',
          ask: '我们的关系里，亲密、激情、承诺这三样各剩下多少？',
          sources: [
            { label: 'Sternberg (1986), Psychological Review 93(2):119–135', url: 'https://doi.org/10.1037/0033-295X.93.2.119' },
            { label: 'Wiley Blackwell 家庭研究百科：三角理论条目', url: 'https://onlinelibrary.wiley.com/doi/abs/10.1002/9781119085621.wbefs058' }
          ]
        },
        {
          name: '激情爱与伴侣爱',
          en: 'Passionate vs. Companionate Love',
          who: 'Elaine Hatfield、Ellen Berscheid 一系',
          year: '1970 年代（常见引用）',
          core: '把爱分成两类：激情爱是强烈的渴望、生理唤醒与患得患失；伴侣爱是深沉的依恋、相互依赖与温情。',
          evidence: '这个二分被后续大量自陈量表操作化，是关系研究里最常用的分类之一。具体效应量未能核实。',
          caveat: '两者不是「必然先后」的阶段：长期关系里激情也可能回升。把激情的自然回落直接解读成「不爱了」，是超出证据的推论。',
          inapp: '「上头」和「安定」在消息数据上几乎无法区分——本项目的分数只数行为，不辨动机，两种情况都可能得高分。',
          ask: '现在的平静是伴侣爱，还是我在自我安慰？',
          sources: [
            { label: 'Routledge：Passionate and Companionate Love', url: 'https://www.taylorfrancis.com/entries/10.4324/9780367198459-REPRW47-1/passionate-companionate-love-amy-canevello-kirby-magid' }
          ]
        },
        {
          name: '爱情颜色（六种爱情风格）',
          en: 'The Colours of Love / Love Styles',
          who: 'John Alan Lee',
          year: '1973（常见引用）',
          core: '把爱情风格比作颜色，提出六种：浪漫之爱（Eros）、游戏之爱（Ludus）、友谊之爱（Storge）、实用之爱（Pragma）、占有之爱（Mania）、利他之爱（Agape）。',
          evidence: '该框架经 Hendrick 与 Hendrick 的「爱态度量表」操作化，成为可测量的六个维度，是该领域常用的测量工具之一。具体信效度数据未能核实。',
          caveat: '六种风格可以并存，不是互斥的「类型」；用它做配对兼容性判断没有依据。',
          inapp: '本项目的四种类型（殉道／镜像／弄臣／幻恋）借用了这种「风格化」的表述，但它其实是取五维里数值最高的一项得来的，不是心理测量结果。',
          ask: '我这样付出，是利他之爱，还是占有之爱？',
          sources: [
            { label: 'De Gruyter：Styles of Romantic Love', url: 'https://www.degruyterbrill.com/de/document/doi/10.12987/9780300159318-008/html' },
            { label: 'Love Attitudes Scale（Hendrick 简版，量表说明）', url: 'https://www.psytoolkit.org/survey-library/love-styles-hendrick-sf.html' }
          ]
        }
      ]
    },

    {
      mark: '二',
      title: '依恋与内在工作模型',
      note: '同一句冷淡的话，在不同人身上会引出完全不同的反应——这一类理论回答的是「为什么」。',
      items: [
        {
          name: '依恋理论与陌生情境',
          en: 'Attachment Theory & the Strange Situation',
          who: 'John Bowlby；Mary Ainsworth（紊乱型由 Mary Main 与 Judith Solomon 补充）',
          year: '1960–1970 年代',
          core: '婴儿与主要照料者的互动会形成一套「依恋行为系统」：照料者是否可及、是否敏感，决定了孩子在压力下寻求安慰的方式。Ainsworth 用「陌生情境」实验把 12 个月大婴儿的依恋编码为安全、焦虑-矛盾、回避三类，后来 Main 与 Solomon 补充了「紊乱型」。',
          evidence: '陌生情境的可操作性由 Ainsworth 与 Bell（1970）确立；van IJzendoorn 与 Kroonenberg（1988）的跨文化元分析是「依恋分类是否跨文化普遍」的标准引用来源；Fraley（2002）的元分析发现依恋安全性在生命前 19 年只是「中等程度稳定」，且更符合「原型式」而非固定不变的动力学。以上具体百分比与效应量均未能核实。',
          caveat: '陌生情境是为 12 个月左右的婴儿设计的范式，外推到成人或「人格类型」已超出适用范围。「紊乱型」不是第四种气质类型，而是「无编码可用」的状态分类，性质与前三类不同。',
          inapp: '依恋框架解释了为什么同一句冷淡的话会引出完全不同的反应——这也是本项目只描述行为、不判断「谁对谁错」的原因。',
          ask: '我每次追问的时候，到底在怕什么？',
          sources: [
            { label: 'Ainsworth & Bell (1970), Child Development 41(1)', url: 'https://doi.org/10.2307/1127388' },
            { label: 'van IJzendoorn & Kroonenberg (1988), Child Development 59(1):147–156', url: 'https://doi.org/10.2307/1130396' },
            { label: 'Fraley (2002), 依恋稳定性元分析', url: 'https://doi.org/10.1207/s15327957pspr0602_03' },
            { label: 'Granqvist et al. (2017), 紊乱型依恋综述', url: 'https://doi.org/10.1080/14616734.2017.1354040' }
          ]
        },
        {
          name: '成人依恋：把恋爱当作依恋过程',
          en: 'Romantic Love as an Attachment Process',
          who: 'Cindy Hazan & Phillip R. Shaver',
          year: '1987',
          core: '成人的浪漫之爱可以理解为同一个依恋行为系统在运作：伴侣互为「依恋对象」，婴儿期的三种依恋模式在恋爱中以对应形式重现。',
          evidence: '这是成人依恋领域引用量最高的奠基文献之一，后续的成人依恋自陈量表几乎都从它出发（题录与 DOI 已核实）。具体样本量与百分比未能核实。',
          caveat: '它用的是「三分类」自陈题，后来已被两维度（焦虑、回避）模型取代，引用时要说清这是 1987 年的测量框架。依恋风格的关系特异性很强——同一个人在伴侣、母亲、挚友面前可能呈现不同模式；稳定性也只是「中等」。所谓「依恋类型是终身标签」没有依据。',
          inapp: '名册里存的是「对方说过什么」，不是「对方是什么依恋类型」——这个区分是刻意的。',
          ask: '我是不是把小时候的那套模式带进了这段关系？',
          sources: [
            { label: 'Hazan & Shaver (1987), JPSP 52(3):511–524', url: 'https://doi.org/10.1037/0022-3514.52.3.511' },
            { label: 'Fraley et al. (2015), 依恋是类别还是维度', url: 'https://doi.org/10.1037/pspp0000027' }
          ]
        },
        {
          name: '焦虑—回避陷阱',
          en: 'Anxious–Avoidant Trap',
          who: '成人依恋领域逐步积累的研究方向（非单篇理论）',
          year: '1990 年代起',
          core: '焦虑者靠放大信号（追问、确认、抗议行为）降低不确定感，回避者靠压制信号（撤退、独处、淡化需求）恢复自主感。两种策略互相触发，也互相验证了对方最怕的那个预期。',
          evidence: '相关元分析（Li & Chan, 2012）比较了焦虑与回避以不同方式影响关系质量；另有双人模型研究（Bretaña 等, 2022）检验「回避 → 退缩—攻击模式 → 满意度」的路径。具体效应量未核实。',
          caveat: '「焦虑型与回避型天生一对、注定失败」缺乏证据：依恋风格的「选型配对」效应在文献中通常被报告为很弱甚至接近零，人并不是系统性地按依恋类型挑伴侣。更稳妥的说法是——当这种配对真的出现时，满意度更低、互动更不稳定。依恋焦虑与回避本身是连续维度，贴上标签再做命运断言是范畴化谬误。',
          inapp: '「连续发送倾向」和「低姿态语言密度」在行为层面接近所谓「过度激活策略」，但它们只是行为频次，不能反过来推断依恋类型。',
          ask: '我们是不是在互相验证对方最怕的那件事？',
          sources: [
            { label: 'Li & Chan (2012), 焦虑与回避如何影响关系质量（元分析）', url: 'https://doi.org/10.1002/ejsp.1842' },
            { label: 'Kirkpatrick & Davis (1994), JPSP 66(3):502–512', url: 'https://doi.org/10.1037/0022-3514.66.3.502' },
            { label: 'Bretaña, Alonso-Arbiol & Recio (2022), Frontiers in Psychology', url: 'https://doi.org/10.3389/fpsyg.2021.794942' }
          ]
        }
      ]
    },

    {
      mark: '三',
      title: '互动与冲突',
      note: '关系不是靠「不吵架」维持的——这一类研究看的是两个人之间实际发生了什么。',
      items: [
        {
          name: '四个骑士与正面互动比例',
          en: 'The Four Horsemen & the Magic Ratio',
          who: 'John Gottman 与 Robert Levenson 的系列纵向研究',
          year: '1980 年代起',
          core: '关系稳定的关键不是没有冲突，而是正面互动与负面互动的比例，以及冲突中能否发出、又能否接住「修复尝试」。观察研究里反复出现的四种破坏性互动被总结为：批评、蔑视、防御、冷战。',
          evidence: '「约 5:1」这个正面／负面比例出自 Gottman 与 Levenson 的多项纵向研究，是该领域流传最广的经验结论之一。具体系数、随访年限与统计结果未能核实，因此本页不给精确数值。',
          caveat: '「四骑士」是描述性总结，不是诊断清单；5:1 也不是精确阈值。把它当成公式去数对方犯了几条，属于误用。',
          inapp: '本项目测不了「正面／负面比例」——那需要对互动质量做编码。它能测的只是谁发得多。所以分数高不等于关系差，只说明这段对话里你更主动。',
          ask: '我们之间还有「修复尝试」吗？',
          sources: [
            { label: 'Gottman Institute：The Magic Relationship Ratio（机构官方说明）', url: 'https://www.gottman.com/blog/the-magic-relationship-ratio-according-science/' },
            { label: 'Essex 大学学位论文中对 Gottman & Levenson 系列纵向研究的综述', url: 'https://repository.essex.ac.uk/43037/1/V_Hillhouse%20Dissertation.pdf' }
          ]
        },
        {
          name: '追逃循环：要求—退缩模式',
          en: 'Demand–Withdraw Pattern',
          who: 'Andrew Christensen 及其同事',
          year: '1990 年前后',
          core: '冲突中一方不断要求、批评或施压，另一方不断回避、沉默或撤退，形成自我强化的循环。Christensen 的核心论点是：决定「谁追谁逃」的主要是冲突结构（谁想改变、谁想维持现状），而不是性别。',
          evidence: '系列研究比较了非困扰伴侣、临床伴侣与离婚伴侣的沟通模式（Christensen & Shenk, 1991），说明要求—退缩在关系恶化的样本中更突出。具体统计结果未能核实。',
          caveat: '要纠正一处常见的归属错误：这一模式的实证研究主体是 Christensen 团队，不是 Sue Johnson——Johnson 的贡献是把它纳入情绪聚焦疗法的临床语言。另外「男的必然逃、女的必然追」是过度简化；横断研究也无法区分因果方向。',
          inapp: '「连续发送倾向」就是「追」留下的行为痕迹。但一段循环需要时间线才看得出来，而本项目目前只分析单次片段——这是它明确的局限。',
          ask: '我们谁在追、谁在退，又是谁在决定「要不要改变」？',
          sources: [
            { label: 'Christensen & Heavey (1990), JPSP 59(1):73–81', url: 'https://doi.org/10.1037/0022-3514.59.1.73' },
            { label: 'Heavey, Layne & Christensen (1993), JCCP 61(1):16–27', url: 'https://doi.org/10.1037/0022-006X.61.1.16' },
            { label: 'Christensen & Shenk (1991), JCCP 59(3):458–463', url: 'https://doi.org/10.1037/0022-006X.59.3.458' }
          ]
        },
        {
          name: '情绪聚焦疗法（EFT）',
          en: 'Emotionally Focused Therapy',
          who: 'Sue Johnson 与 Les Greenberg',
          year: '1980 年代（首个对照研究 1985）',
          core: '伴侣冲突的根源往往不是沟通技巧不足，而是依恋层面的情绪信号没有被接住。治疗通过重构「负向互动循环」，让双方在情绪层面重新建立安全联结。',
          evidence: '一项只纳入随机对照试验的元分析（33 项研究、2,730 名参与者）给出的数字是：后测整体 g = 0.60（行为伴侣治疗 BCT 为 0.53、EFT 为 0.73）；6 个月随访整体 g = 0.44；12 个月的效果未能维持（仅 BCT 有数据，g = 0.06）。EFT 与 BCT 之间没有显著差异，作者同时提示可能存在发表偏倚。',
          caveat: '中文科普常把「EFT 是唯一有效的伴侣疗法」当成结论，这与上述元分析不符。另外 Sue Johnson 的伴侣疗法（EFCT）与 Greenberg 发展的个体情绪聚焦疗法同用「EFT」缩写，适用对象不同，极易混淆。',
          inapp: '本项目不做治疗，也不给「该不该继续」的结论。真需要介入时，一次一对一的伴侣治疗评估，比任何分数都更值得。',
          ask: '如果我们去做伴侣咨询，应该期待什么、又能期待多久？',
          sources: [
            { label: 'Johnson & Greenberg (1985), JCCP 53(2):175–184', url: 'https://doi.org/10.1037/0022-006X.53.2.175' },
            { label: 'Rathgeber et al., 伴侣治疗随机对照试验元分析（JMFT）', url: 'https://doi.org/10.1111/jmft.12336' }
          ]
        },
        {
          name: '感知到的伴侣回应性',
          en: 'Perceived Partner Responsiveness',
          who: 'Harry Reis, Margaret Clark 与 John Holmes',
          year: '2004（常见引用）',
          core: '关系质量的核心不只是对方做了多少，而是你是否「感到」自己的需要被看见、被理解、被珍视。',
          evidence: '该章节系统整理了回应性与亲密感、满意度之间的关系，是关系科学里被反复使用的核心构念。具体效应量未能核实。',
          caveat: '它测的是知觉，不是客观行为，因此与「对方实际做了多少」常常对不上——很多争执正源于这个落差。',
          inapp: '「对话衔接度」测的是行为层面的接不接话，只能算回应性的一个粗糙代理，不能等同于「你有没有被理解」。',
          ask: '我到底是想让对方做什么，还是只想让他知道我现在很难？',
          sources: [
            { label: 'Reis, Clark & Holmes (2004)：Perceived Partner Responsiveness（作者站点 PDF）', url: 'http://www.sas.rochester.edu/psy/people/faculty/reis_harry/assets/pdf/ReisClarkHolmes_2004.pdf' }
          ]
        }
      ]
    },

    {
      mark: '四',
      title: '承诺与投入',
      note: '为什么付出越多反而越难抽身——这一类理论解释的是「留下来」的机制。',
      items: [
        {
          name: '投资模型',
          en: 'Investment Model',
          who: 'Caryl E. Rusbult',
          year: '1980（1983 年做了纵向检验）',
          core: '关系承诺由三样东西决定：满意度（想不想留）、替代方案质量（还有没有别的选择）、投资大小（已经投进去多少、离开会损失什么）。满意度低不等于会走——因为投资高、替代差。',
          evidence: '这是本页里实证基础最扎实的一条：两份独立的元分析支持该模型（Le & Agnew 2003；Tran 等 2019）。原始研究与其纵向检验的题录、DOI 均已核实；元分析中的具体效应量数值未能核实。',
          caveat: '证据主体是相关与纵向研究，仍高度依赖自我报告；「投资」在集体主义或包办婚姻语境里含义不同；已婚样本中「替代方案质量」的差异本来就小。',
          inapp: '本项目能测「你比对方主动多少」，可以看成满意度与投资失衡的行为痕迹；但它测不到你的替代方案质量，所以不能预测你会不会离开。',
          ask: '我留下是因为想留，还是因为走不了？',
          sources: [
            { label: 'Rusbult (1980), JESP 16(2):172–186', url: 'https://doi.org/10.1016/0022-1031(80)90007-4' },
            { label: 'Rusbult (1983), JPSP 45(1):101–117（纵向检验）', url: 'https://doi.org/10.1037/0022-3514.45.1.101' },
            { label: 'Le & Agnew (2003), 投资模型元分析', url: 'https://doi.org/10.1111/1475-6811.00035' },
            { label: 'Tran, Judge & Kashima (2019), 投资模型元分析更新', url: 'https://doi.org/10.1111/pere.12268' }
          ]
        },
        {
          name: '社会交换理论',
          en: 'Social Exchange Theory',
          who: 'John W. Thibaut & Harold H. Kelley',
          year: '1959',
          core: '关系被理解为报酬与成本的交换。「比较水平」（CL）决定你满不满意，「替代比较水平」（CLalt）决定你依不依赖。满意与依赖是两件事：可以在不满意的关系里留下，也可能在没有不满意的关系里离开。',
          evidence: '这是理论著作而非实证论文；其中的 CL／CLalt 框架被投资模型继承并做了量化检验。',
          caveat: '把亲密关系建模成成本收益计算长期受到批评——它忽略了爱、义务与道德承诺；CL 与 CLalt 都是主观测量且随情境漂移。它更适合当分析框架，而不是可证伪的预测模型。',
          inapp: '这也正是本项目不给「该不该分手」建议的原因：分数只反映交换的一侧，看不到你的替代方案与责任。',
          ask: '我现在是「不满意但走不了」吗？',
          sources: [
            { label: 'Thibaut & Kelley (1959), The Social Psychology of Groups（重印版）', url: 'https://doi.org/10.4324/9781315135007' },
            { label: 'Oxford Reference：comparison level（工具书条目）', url: 'https://www.oxfordreference.com/display/10.1093/oi/authority.20110803095628681' }
          ]
        },
        {
          name: '公平理论',
          en: 'Equity Theory',
          who: 'J. Stacy Adams',
          year: '1965',
          core: '人会比较自己的「投入／产出比」与他人的比值，失衡会带来不公平感，并促使人改变投入、改变认知或离开。用在亲密关系上，过度受益与受益不足都可能让人不舒服，公平状态预测最高满意度。',
          evidence: 'Adams (1965) 是组织与交换场景中的经典。关系领域的检验结论并不一致：多项研究只发现「受益不足」与不满稳定相关，「过度受益」的效应较弱或不稳定。',
          caveat: '「公平」的判断标准主观、且受文化规范影响。把公平理论当成「谁付出多谁就占理」的判据，是误用。',
          inapp: '「小丑指数」在概念上就是感知失衡的量化尝试——但本项目的五维只数行为，不衡量你主观上觉得值不值。',
          ask: '我是在追求公平，还是在讨一个肯定？',
          sources: [
            { label: 'Adams (1965), Inequity in Social Exchange', url: 'https://doi.org/10.1016/S0065-2601(08)60108-2' }
          ]
        },
        {
          name: '沉没成本与承诺升级',
          en: 'Sunk Cost & Escalation of Commitment',
          who: 'Barry M. Staw；Hal Arkes 与 Catherine Blumer',
          year: '1976 / 1985',
          core: '已经付出且收不回的成本本不该影响接下来的决定，但人往往因为「已经投入这么多」而继续投入，这就是承诺升级。',
          evidence: 'Staw (1976) 发现对失败项目负有责任的人会追加更多资源；Arkes 与 Blumer (1985) 用一系列实验证明了沉没成本效应。把它们直接移植到亲密关系的专门实验效应量未能核实——关系里可核实的对应机制是投资模型。',
          caveat: '把「留下来」一律称作谬误是错的：留下可能出于义务、子女、经济依赖或信仰，也可能因为关系真的在变好。这个概念在科普里最容易被拿来评判别人的选择，包括用来劝人分手。',
          inapp: '名册里的「投食次数」其实是一份投资记录——它只说明你花了多少时间，不说明这段关系值不值得。',
          ask: '我坚持的是这段关系，还是我已经付出的那些时间？',
          sources: [
            { label: 'Staw (1976), OBHDP 16(1):27–44', url: 'https://doi.org/10.1016/0030-5073(76)90005-2' },
            { label: 'Arkes & Blumer (1985), OBHDP 35(1):124–140', url: 'https://doi.org/10.1016/0749-5978(85)90049-4' }
          ]
        }
      ]
    },

    {
      mark: '五',
      title: '吸引、记忆与上瘾',
      note: '那些让人「上头」的机制，多数在关系开始之前就已经在起作用了。',
      items: [
        {
          name: '吊桥效应与唤醒的错误归因',
          en: 'Misattribution of Arousal',
          who: 'Donald G. Dutton & Arthur P. Aron',
          year: '1974',
          core: '生理唤醒（比如恐惧带来的心跳加速）如果被错误地归因于眼前的人，就可能被体验为吸引。经典操作是：在高悬吊桥上由女性实验者向男性被试搭话并留下电话，与低矮稳固的桥面对照。',
          evidence: '可核实的是方向性结论：高唤醒条件下的吸引指标更高。广为流传的「高焦虑组约 50%、对照组约 12.5%」这类具体百分比未能从原始文献核实，因此本页不写数字。',
          caveat: '方法学质疑长期存在：两组在年龄、桥面宽度、等待时间上并不匹配，存在选择偏差；样本小、只有单次实验；后续研究证据整体混合。',
          inapp: '「一起做点刺激的事会更好」这类建议就源自这里——方向可以听，但别把它当作确定的机制。',
          ask: '我对他心动，是因为他，还是因为那天那个场合？',
          sources: [
            { label: 'Dutton & Aron (1974), JPSP 30(4):510–517', url: 'https://doi.org/10.1037/h0037031' }
          ]
        },
        {
          name: '单纯曝光效应',
          en: 'Mere Exposure Effect',
          who: 'Robert B. Zajonc（元分析：Robert Bornstein）',
          year: '1968 / 1989',
          core: '对某个刺激的重复接触——即使没有任何强化——也会提高对它的喜爱程度，即「熟悉带来喜欢」，为「朝夕相处产生好感」提供了机制解释。',
          evidence: 'Bornstein (1989) 综合 1968–1987 年的全部相关研究，结论是该效应稳定存在，通常被描述为小到中等强度的正效应。具体平均效应量未能核实，本页不给数字。',
          caveat: '边界条件很重要：如果刺激一开始就被负向评价，重复曝光可能加深厌恶；曝光次数过多还会出现倒 U 型下降，且无意识呈现时效应反而更强。把它等同于「死缠烂打就能追到人」是典型误用。',
          inapp: '名册记录的每一次接触都在累积熟悉度——但这只说明「见面有意义」，不说明「多见面就能改变结果」。',
          ask: '他对我的好感，是真的，还是只是习惯了我的存在？',
          sources: [
            { label: 'Zajonc (1968), JPSP 9(2):1–27', url: 'https://doi.org/10.1037/h0025848' },
            { label: 'Bornstein (1989), Psychological Bulletin 106(2):265–289（元分析）', url: 'https://doi.org/10.1037/0033-2909.106.2.265' }
          ]
        },
        {
          name: '自我扩张模型',
          en: 'Self-Expansion Model',
          who: 'Arthur Aron & Elaine N. Aron',
          year: '1986',
          core: '人有扩张自我（能力、资源、身份、视角）的基本动机。恋爱时伴侣被「纳入」自我，关系带来快速的自我扩张与愉悦；当关系不再提供新的扩张机会，激情与满意度就会下降——一起做新颖且具唤醒性的活动可以重新激活它。',
          evidence: 'Aron 等（1991）为「把他人纳入自我」提供了方法学基础（IOS 量表）；Aron 等（2000）的实验检验了新颖活动对关系质量的作用。具体效应量未能核实。',
          caveat: '证据以中等规模实验与相关研究为主，存在发表偏倚与小样本的风险；集体主义文化里「自我」的边界不同，扩张动机的表现也可能不同。「一起蹦极就能救关系」是过度简化。',
          inapp: '本项目只数消息，看不到你们是否在一起经历新东西——而这恰恰是分数之外更重要的部分。',
          ask: '我们最近一起做过什么新鲜事吗？',
          sources: [
            { label: 'Aron et al. (1991), JPSP 60(2):241–253', url: 'https://doi.org/10.1037/0022-3514.60.2.241' },
            { label: 'Aron et al. (2000), JPSP 78(2):273–284（新颖活动实验）', url: 'https://doi.org/10.1037/0022-3514.78.2.273' },
            { label: 'Aron & Aron (1996), Personal Relationships 3(1):45–58', url: 'https://doi.org/10.1111/j.1475-6811.1996.tb00103.x' }
          ]
        },
        {
          name: '米开朗基罗现象',
          en: 'Michelangelo Phenomenon',
          who: 'Stephen M. Drigotas, Caryl E. Rusbult 等',
          year: '1999',
          core: '伴侣会通过日常肯定与反馈，帮助或阻碍对方成为其「理想自我」。当伴侣知觉到的你的理想自我与你的实际行为一致时，你会朝那个方向移动，关系与个人适应都更好。',
          evidence: '原始研究包含多项研究（含纵向设计），题录与 DOI 已核实。具体效应量与纵向系数未能核实。',
          caveat: '研究集中在 Rusbult 学派，独立实验室的重复有限；「理想自我」由本人自报，未必代表对本人真正有利的方向；样本主要是美国大学生与已婚异性恋伴侣，跨文化推广需谨慎。',
          inapp: '名册里存的是「对方说过什么喜好」——记录的是既有事实，不是「对方希望你成为谁」。后者本页不建议你替对方推断。',
          ask: '这段关系让我更像我想成为的人了吗？',
          sources: [
            { label: 'Drigotas et al. (1999), JPSP 77(2):293–323', url: 'https://doi.org/10.1037/0022-3514.77.2.293' }
          ]
        },
        {
          name: '间歇性强化（忽冷忽热）',
          en: 'Intermittent Reinforcement',
          who: 'B. F. Skinner 的强化程序表；恋爱语境的用法是流行化外推',
          year: '学习理论 1930–50 年代；恋爱版本无单一出处',
          core: '要分两层看。学习理论层面：部分强化（间歇强化）比连续强化产生更强的「抗消退性」——行为在不再被强化之后消失得更慢（PREE）。恋爱层面：把伴侣的忽冷忽热类比为间歇强化，用来解释为什么这种关系更难抽身。',
          evidence: '第一层（PREE）是学习心理学里最稳固的现象之一，动物与人类实验都有大量证据。第二层在同行评审文献里没有直接的实证支持——它主要出现在临床观察、科普与自助读物中；最接近的学术线索是「分分合合关系」研究（Dailey 等 2009、2011），而不是「间歇性强化」框架本身。',
          caveat: '概念并不等价：强化程序表定义在明确、可计数的「行为—强化物」配对上，而忽冷忽热是模糊、多义、需要接收者主观解读的社交信号，两者不是同一个构念；「上瘾」也不是依恋研究里的既定术语。更要紧的是——把所有关系问题归因于「我被间歇强化上瘾了」，会掩盖真实的胁迫、控制与暴力议题，那些需要的是安全干预，不是强化程序表分析。',
          inapp: '「他偶尔回我一句，我就又能撑很久」——这种模式在本项目里会表现为很高的连续发送倾向；但分数无法判断这是忽冷忽热，还是对方只是真的忙。',
          ask: '我放不下的是他，还是那种偶尔被回应的感觉？',
          sources: [
            { label: 'Dailey et al. (2009), Personal Relationships 16(1):23–47', url: 'https://doi.org/10.1111/j.1475-6811.2009.01208.x' },
            { label: 'Dailey et al. (2011), The Journal of Social Psychology 151(4):417–440', url: 'https://doi.org/10.1080/00224545.2010.503249' }
          ]
        },
        {
          name: '蔡格尼克效应（附重要反证）',
          en: 'Zeigarnik Effect',
          who: 'Bluma Zeigarnik（反证：Ghibellini & Meier 元分析）',
          year: '1927；2025 年被重新检验',
          core: '流传最广的版本是：被中断、未完成的事比已完成的事更容易被记住，所以「未了之事」总萦绕心头，暗恋也因此比分手更难放下。',
          evidence: '2025 年一项元分析重新检验了这个效应，结论是：未完成任务并没有出现记忆优势，蔡格尼克效应「缺乏普适性」；相对稳健的反而是「未完成任务更容易被重新拾起」，即奥夫西安金娜效应。原文摘要的表述是 the Zeigarnik effect lacks universal validity。',
          caveat: '中文科普几乎都把它当作「已被证明的定律」，但重复检验并不支持。要写只能说「在特定情境与实验条件下可能出现」——这是一个典型的、被过度传播的心理学效应。',
          inapp: '「为什么暗恋比分手更难放下」这个说法在本页不成立，因为它依赖的正是那个不稳固的效应。本项目也不对「放不下」做任何量化。',
          ask: '我忘不掉的是那个人，还是那件没做完的事？',
          sources: [
            { label: 'Ghibellini & Meier (2025), 蔡格尼克与奥夫西安金娜效应元分析（开放获取）', url: 'https://www.nature.com/articles/s41599-025-05000-w' }
          ]
        }
      ]
    },

    {
      mark: '六',
      title: '流行，但实证支持有限',
      note: '把这些单独放一组，是为了提醒：流传很广不等于证据充分。',
      items: [
        {
          name: '五种爱的语言',
          en: 'The Five Love Languages',
          who: 'Gary Chapman',
          year: '1992',
          core: '人用五种方式表达与接收爱：肯定的言语、优质时间、礼物、服务行动、身体接触；每人有一个主要爱语，伴侣「说你的爱语」应当提升满意度。',
          evidence: '证据基本是否定性的。关系科学的综述（Impett, Park & Muise 2024）与 APS 的教学评述指出三点：人们普遍重视全部五种方式，而非只有一种；五种「语言」之间存在大量重叠；即使用 Chapman 自己的测量，「匹配」与关系满意度之间也没有一致的正相关——相反，所有爱的表达方式都与更高的满意度相关。相关检验研究（Flicker & Sancier-Barbosa 2025；Flicker 等 2025）也对它的结构效度提出质疑。综述作者建议的替代隐喻是「爱像均衡饮食」：需要多种关系营养长期均衡供给。',
          caveat: '三个核心假设（存在单一主要爱语、五种语言互相独立、匹配能提升满意度）都没有得到支持，最后一条甚至有反向证据。作为沟通与自我反思的隐喻它很好用；作为经过检验的理论或是「关系诊断工具」，则不成立。',
          inapp: '名册记录的是「对方明确说过喜欢什么」——这是具体事实，比「他属于哪种爱语」可靠得多。',
          ask: '我是不是在用我以为的方式爱他，而不是他需要的方式？',
          sources: [
            { label: 'Impett, Park & Muise (2024), Current Directions in Psychological Science', url: 'https://doi.org/10.1177/09637214231217663' },
            { label: 'APS Observer：Empirical Evidence Is My Love Language（官方教学评述）', url: 'https://www.psychologicalscience.org/publications/observer/teaching-current-directions-love-languages.html' },
            { label: 'Flicker & Sancier-Barbosa (2025), JMFT（直接检验）', url: 'https://doi.org/10.1111/jmft.12747' }
          ]
        },
        {
          name: '罗密欧与朱丽叶效应',
          en: 'Romeo and Juliet Effect',
          who: 'Richard Driscoll, Keith E. Davis & Milton E. Lipetz（重复检验：Sinclair 等）',
          year: '1972；2014 年重复检验失败',
          core: '来自父母或社会网络的干涉与反对会增强恋人的浪漫情感与承诺——越被反对越相爱。',
          evidence: '1972 年的原始研究确实报告了这一效应；但后续的重新检验基本未能支持它（Sinclair, Hood & Wright 2014）。更符合现有证据的其实是**反向**的社会网络效应：社会支持与更好的关系结果相关，而反对与关系质量下降、分手风险上升相关。',
          caveat: '这是一个著名但未通过重复检验的经典效应。写成「心理学证明越被反对越相爱」是错的——它的现代版本恰恰相反。',
          inapp: '本项目完全看不到你们的外部环境（家人、朋友、距离、经济），所以无法也不应就「该不该继续」给出任何判断。',
          ask: '我们面对的外部压力，是在帮我们还是在耗我们？',
          sources: [
            { label: 'Driscoll, Davis & Lipetz (1972), JPSP 24(1):1–10', url: 'https://doi.org/10.1037/h0033373' },
            { label: 'Sinclair, Hood & Wright (2014), Social Psychology 45(3):170–178（重复检验）', url: 'https://doi.org/10.1027/1864-9335/a000181' },
            { label: 'Sinclair & Ellithorpe (2014)：The New Story of Romeo and Juliet', url: 'https://doi.org/10.1017/cbo9781139333610.010' }
          ]
        }
      ]
    }
  ],

  caveats: [
    '相关不等于因果。这些研究大多来自问卷与横断数据，它们说明「同时出现」，不说明「谁导致了谁」。满意度低与投入高同时出现，不意味着「投入造成了痛苦」。',
    '群体规律不等于你面前这个人。效应量通常不大，个体差异与文化差异往往比理论本身更大——「平均而言」不等于「对你而言」。',
    '别把类型当标签。「焦虑型」「回避型」描述的是倾向与情境反应，不是终身身份，更不是给伴侣下判决的依据；依恋的安全性在成年后只是「中等程度稳定」。',
    '注意证据等级。投资模型有两次独立元分析支持；而五种爱的语言、罗密欧与朱丽叶效应、以及「忽冷忽热＝间歇性强化成瘾」都证据薄弱甚至已被否定。把它们并列陈述会给人一种错误的力量感。',
    '注意样本与时代。不少经典研究的样本是 20 世纪后半叶的北美大学生与已婚异性恋伴侣，「父母干涉」「替代方案」「自我扩张」在别的文化语境里含义与权重都会变，跨文化推广大多未经检验。',
    '警惕重复性危机。吊桥效应样本小、组间不匹配；蔡格尼克效应在 2025 年的元分析里未发现普适的记忆优势。面对取不到原文的数字，正确做法是不写，而不是补一个看起来合理的。',
    '理论不给处方。知道依恋类型不会告诉你该不该分手；「这是沉没成本谬误，你应该走」这类说法，是把复杂过程压缩成单向诊断，常被用来施压。',
    '本项目的分数不是测量工具。它是一个课程作业里的趣味算法，不能当心理评估，更不能当作去质问对方的「证据」。'
  ]
};
