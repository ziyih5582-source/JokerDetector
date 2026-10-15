from openai import OpenAI

#create clint
clint = OpenAI(
    api_key = "sk-xxxxxxxxxxx",
    base_url = "https://models.sjtu.edu.cn/api/v1"
)

#get response 
response = clint.chat.completions.create(
    model = "deepseek-chat",
    messages = [
        {"role": "system", "content":"You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"}
    ]
)

print(response.choices[0].message.content)