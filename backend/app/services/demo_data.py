# -*- coding: utf-8 -*-
"""
Demo 数据：内置几组经典"小丑案例"聊天记录，无需上传文件即可演示
"""

# ==================== 案例 1：标准舔狗小丑 ====================
DEMO_SIMP = {
    "title": "🐶 案例一：标准舔狗型",
    "description": "单方面疯狂输出，对方爱答不理，典型自我感动式小丑",
    "self_name": "阿强",
    "other_name": "小美",
    "messages": [
        {"speaker": "阿强", "content": "早上好呀！今天天气真好☀️"},
        {"speaker": "阿强", "content": "你吃早饭了吗？我给你带了面包"},
        {"speaker": "小美", "content": "吃了"},
        {"speaker": "阿强", "content": "那就好那就好！对了你昨天说的那个电影，我查了一下，今晚7点有场次"},
        {"speaker": "阿强", "content": "要不要一起去看呀？[可爱]"},
        {"speaker": "小美", "content": "今晚有事"},
        {"speaker": "阿强", "content": "没关系没关系！那明天呢？后天也行！"},
        {"speaker": "阿强", "content": "或者你喜欢看什么类型的？我都可以的！"},
        {"speaker": "小美", "content": "再说吧"},
        {"speaker": "阿强", "content": "好好好，那你想看的时候告诉我！"},
        {"speaker": "阿强", "content": "对了对了，我今天看到一只猫，好可爱[图片]"},
        {"speaker": "阿强", "content": "跟你好像哈哈哈"},
        {"speaker": "小美", "content": "..."},
        {"speaker": "阿强", "content": "你是不是心情不好呀？"},
        {"speaker": "阿强", "content": "我是不是说错什么了？对不起对不起"},
        {"speaker": "阿强", "content": "我不太会说话，你别生气"},
        {"speaker": "小美", "content": "没有"},
        {"speaker": "阿强", "content": "那就好！你今天穿的真好看（虽然还没见到你但我知道）"},
        {"speaker": "阿强", "content": "晚上记得早点睡哦，不要熬夜"},
        {"speaker": "阿强", "content": "晚安！[月亮]"},
        {"speaker": "阿强", "content": "啊不对现在才下午，那就下午好！"},
        {"speaker": "小美", "content": "嗯"},
        {"speaker": "阿强", "content": "那个...我在想我们以后可以一起去很多地方"},
        {"speaker": "阿强", "content": "你有没有想去的地方呀？"},
        {"speaker": "阿强", "content": "我都可以的，听你的！"},
        {"speaker": "小美", "content": "随便"},
        {"speaker": "阿强", "content": "好的好的，那我先做做攻略！"},
        {"speaker": "阿强", "content": "你不用管我的，我自己看看就行"},
        {"speaker": "阿强", "content": "只要你开心就好"},
    ]
}

# ==================== 案例 2：自我贬低弄臣型 ====================
DEMO_JESTER = {
    "title": "🎭 案例二：自嘲弄臣型",
    "description": "靠自我贬低博取关注，用搞笑掩饰不安全感",
    "self_name": "大伟",
    "other_name": "阿琳",
    "messages": [
        {"speaker": "大伟", "content": "哈哈哈哈我今天又干了一件蠢事"},
        {"speaker": "大伟", "content": "我真是太菜了"},
        {"speaker": "阿琳", "content": "怎么了"},
        {"speaker": "大伟", "content": "我就是个小丑，别提了[捂脸]"},
        {"speaker": "大伟", "content": "你肯定觉得我这种人很搞笑吧"},
        {"speaker": "阿琳", "content": "还好吧"},
        {"speaker": "大伟", "content": "救命啊我发现我今天穿了两只不一样的袜子"},
        {"speaker": "大伟", "content": "我就说我是个废物吧"},
        {"speaker": "阿琳", "content": "哈哈"},
        {"speaker": "大伟", "content": "你笑了！！！值了值了"},
        {"speaker": "大伟", "content": "我的人生目标就是让你开心"},
        {"speaker": "阿琳", "content": "你也不用这么说自己"},
        {"speaker": "大伟", "content": "没事没事我不配拥有自尊"},
        {"speaker": "大伟", "content": "诶对了你喜欢什么样的人呀"},
        {"speaker": "阿琳", "content": "不知道"},
        {"speaker": "大伟", "content": "我觉得肯定不是我这种的哈哈哈"},
        {"speaker": "大伟", "content": "我就是搞笑担当"},
        {"speaker": "阿琳", "content": "..."},
        {"speaker": "大伟", "content": "我错了我不该问这个，对不起对不起"},
        {"speaker": "大伟", "content": "我还是继续当小丑吧"},
    ]
}

# ==================== 案例 3：健康模式（非小丑） ====================
DEMO_HEALTHY = {
    "title": "👑 案例三：势均力敌型",
    "description": "双方互动均衡，互有推拉，健康的社交模式",
    "self_name": "小陈",
    "other_name": "小雨",
    "messages": [
        {"speaker": "小陈", "content": "昨天那家餐厅确实不错，下次可以试试他们的甜品"},
        {"speaker": "小雨", "content": "对！我看到了隔壁桌的提拉米苏，看起来超棒"},
        {"speaker": "小雨", "content": "你周末有空吗？"},
        {"speaker": "小陈", "content": "周六下午可以，上午有个会"},
        {"speaker": "小雨", "content": "ok那周六下午2点？"},
        {"speaker": "小陈", "content": "可以，要不先去喝咖啡再过去"},
        {"speaker": "小雨", "content": "好的呀！我最近发现了一家新开的咖啡馆"},
        {"speaker": "小陈", "content": "哦？在哪"},
        {"speaker": "小雨", "content": "就在上次那附近，走路5分钟"},
        {"speaker": "小雨", "content": "他们家的手冲听说很不错"},
        {"speaker": "小陈", "content": "行，那先去喝咖啡，我也好久没喝手冲了"},
        {"speaker": "小陈", "content": "对了你上次说的那个项目怎么样了"},
        {"speaker": "小雨", "content": "还在推进中，遇到了一些阻力"},
        {"speaker": "小陈", "content": "需要帮忙的话可以说"},
        {"speaker": "小雨", "content": "谢啦，暂时还能应付"},
        {"speaker": "小雨", "content": "倒是你，上次说想换工作的事，想清楚了吗"},
        {"speaker": "小陈", "content": "还在考虑，不急。想清楚再说"},
        {"speaker": "小雨", "content": "嗯，别急，慢慢来"},
        {"speaker": "小陈", "content": "周六见！"},
        {"speaker": "小雨", "content": "周六见👋"},
    ]
}

# 所有 Demo 案例
DEMO_CASES = [DEMO_SIMP, DEMO_JESTER, DEMO_HEALTHY]
