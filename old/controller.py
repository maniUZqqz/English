# from openai import OpenAI
#
# # تنظیمات کلید API و آدرس پایه
# API_KEY = 'tpsg-B71Vq5F40g0MyYKgDwPaflZWrCY3TPv'
# BaseUrl = 'https://api.metisai.ir/openai/v1'
#
#
#
# conversation_history = [
#     {
#         "role": "system",
#         "content": "You are an English grammar teaching assistant. Your role is to help users understand and improve their English grammar. Provide clear explanations, examples, and corrections when needed."
#     }
# ]
#
# client = OpenAI(
#     base_url=BaseUrl,
#     api_key=API_KEY,
# )
#
# while True:
#     user_input = input("Enter your English grammar question (or type 'exit' to quit): ")
#     if user_input.lower() == 'exit':
#         print('End task')
#         break
#
#     conversation_history.append(
#         {
#             "role": "user",
#             "content": user_input
#         }
#     )
#
#     response = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=conversation_history
#     )
#
#     # تبدیل پاسخ به دیکشنری
#     response_dict = response.to_dict()
#
#     conversation_history.append(
#         {
#             "role": "assistant",
#             "content": response.choices[0].message.content
#         }
#     )
#
#     # استخراج فقط پاسخ
#     answer = response_dict['choices'][0]['message']['content']
#     print("Answer:", answer)
#
#
#
#
#
#
#
#
#
