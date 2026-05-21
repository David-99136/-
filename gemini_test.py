from google import genai

# 使用最新版 Client 進行初始化
client = genai.Client(api_key="AIzaSyC9hlOOH9Uz2TKsJVYbQFt1yuzmq3vIHxg")

# 呼叫最新穩定的 gemini-2.5-flash 模型
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='你好！如果你看到這句話，代表我們成功在本地端連線了！',
)

print(response.text)