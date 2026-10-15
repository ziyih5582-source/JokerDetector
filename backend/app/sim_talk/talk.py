from openai import OpenAI

history = [{"role": "system", "content":"You are a helpful assistant."}]

#creat clint
clint = OpenAI(
    api_key = "sk-xxxxxxxxx",
    base_url = "https://models.sjtu.edu.cn/api/v1"
)

#create talk model
while True:
    user_input = input("user: ")
    if user_input in ("quit", "exit"):
        break
    history.append({"role": "user", "content": user_input})
    response = clint.chat.completions.create(
        model = "deepseek-chat",
        messages = history
    )
    ans = response.choices[0].message.content
    print("ans ", ans)
    history.append({"role":"system", "content":ans})