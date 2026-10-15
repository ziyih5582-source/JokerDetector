from openai import OpenAI
import json

#create client
client = OpenAI(
    api_key = "sk-xxxxxxxxxx",
    base_url = "https://api.deepseek.com/v1"
)

#get json file and build request
with open('test_data.json', mode='r', encoding='utf-8') as f:
    data = json.load(f)
data_str = json.dumps(data, ensure_ascii=False, indent=2)
base_message = [{"role":"system", "content":"这里有个 JSON 文件，里面包含了一段对话历史。在接下来的回复里，你要尽全力模仿 Li 的说话风格。注意，你不需要总是顺着用户的话题，完全可以开启新话题。你甚至可以像 Li 那样选择“已读不回”。你可以分享自己的生活，或者表现出开心、难过等真实情绪。你不需要总是去接住对方的情绪。还有，别去重复 Li 说过的话，那样很蠢。总之，你的所有回复都要基于 Li 的说话风格来。"},
           {"role":"system", "content":data_str}]

#get input
user_input = input("You: ")
base_message.append({"role":"user", "content":user_input})

#create response model
versions = ["假定 Li 现在心情很好", "假定 Li 现在心情很糟" ,"假定 Li 现在很冷漠，不像继续这个话题，只做礼仪性的回复"]
for condition in versions:
    response = client.chat.completions.create(
        model = "deepseek-chat",
        messages = base_message + [{"role":"assistant", "content":condition}]
    )
    print(f"--------- {condition} ---------")
    print(response.choices[0].message.content)
    print()
    



