import json
import re
import os
from typing import Dict, List, Union, Any

from openai import OpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt
from dotenv import load_dotenv

load_dotenv()

os.environ['OPENAI_API_KEY'] = os.getenv("hub_api_key")
os.environ['OPENAI_BASE_URL'] = "https://api.openai-hub.com/v1"
client = OpenAI()


def message_template(role: str, content: str) -> Dict[str, str]:
    """创建一个消息模板字典。

    Args:
        role: 消息角色 ('system', 'user', 或 'assistant')
        content: 消息内容

    Returns:
        包含角色和内容的字典
    """
    return {'role': role, 'content': content}


@retry(wait=wait_random_exponential(multiplier=1, max=40),
       stop=stop_after_attempt(3))
def chat_single(messages: List[Dict[str, str]],
                mode: str = "",
                model: str = 'gpt-4o',
                temperature: float = 0,
                verbose: bool = False):
    """发送单个聊天请求到OpenAI API。

    Args:
        messages: 消息列表
        mode: 响应模式 ('stream', 'json', 'json_few_shot', 或空字符串为普通模式)
        model: 要使用的模型
        temperature: 温度参数，控制响应随机性
        verbose: 是否打印详细信息

    Returns:
        根据模式返回不同类型的响应
    """
    if mode == "stream":
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True,
            max_tokens=2560
        )
        return response
    elif mode == "json":
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=temperature,
            messages=messages
        )
        return response.choices[0].message.content
    elif mode == 'json_few_shot':
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=2560
        )
        result = response.choices[0].message.content
        if verbose:
            print(result)
        return extract_json_and_similar_words(result)
    else:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content


def format_list_string(input_str: str) -> str:
    """格式化包含列表的字符串为有效的JSON。

    Args:
        input_str: 包含列表的字符串

    Returns:
        格式化后的JSON字符串
    """
    match = re.search(r'\{\s*"[^"]+"\s*:\s*\[(.*?)\]\s*\}', input_str)
    if not match:
        return "Invalid input format"

    list_content = match.group(1)
    elements = [e.strip() for e in list_content.split(',')]

    formatted_elements = []
    for elem in elements:
        if not re.match(r'^([\'"])(.*)\1$', elem):
            elem = f'"{elem}"'
        formatted_elements.append(elem)

    return f'{{ "similar_words":[{", ".join(formatted_elements)}]}}'


def extract_json_and_similar_words(text: str) -> Dict[str, Any]:
    """从文本中提取JSON数据。

    Args:
        text: 包含JSON数据的文本

    Returns:
        提取的JSON数据字典
    """
    try:
        json_match = re.search(r'```json\s*({.*?})\s*```', text, re.DOTALL)

        if not json_match:
            raise ValueError("No JSON data found in the text.")

        json_str = json_match.group(1)
        if 'similar_words' in text:
            data = json.loads(format_list_string(json_str))
        else:
            data = json.loads(json_str)

        return data
    except Exception as e:
        print(f"Error extracting JSON: {e}")
        return {"error": str(e)}


def run_examples():
    """运行所有模式的示例，展示不同API调用方式。"""

    # 基础消息模板，用于所有示例
    base_messages = [
        message_template('system',
                         'hi'),
    ]

    print("\n===== 1. 标准模式示例 =====")
    standard_messages = base_messages.copy()
    standard_messages.append(
        message_template('user', '你是谁'))

    standard_response = chat_single(standard_messages)
    print(f"响应:\n{standard_response}\n")

    print("\n===== 2. 流式响应模式示例 =====")
    stream_messages = base_messages.copy()
    stream_messages.append(
        message_template('user', '解释Python中的异步编程概念。'))

    stream_response = chat_single(stream_messages, mode="stream")

    collected_response = ""
    print("流式响应:")
    for chunk in stream_response:
        if chunk.choices[0].delta.content is not None:
            content_chunk = chunk.choices[0].delta.content
            collected_response += content_chunk
            print(content_chunk, end="", flush=True)

    print("\n\n完整收集的响应:")
    print(collected_response)

    print("\n===== 3. JSON响应模式示例 =====")
    json_messages = base_messages.copy()
    json_messages.append(message_template('user',
                                          '以JSON格式提供Python三个主要数据结构的名称和简短描述。'))

    json_response = chat_single(json_messages, mode="json")
    print(f"JSON响应:\n{json_response}\n")
    print(f"解析后的JSON:\n{json.loads(json_response)}\n")

    print(
        "\n===== 4. JSON Few-Shot示例 =====")  # 可以保留reasoning部分，减少结构输出文本导致的Performance下降
    few_shot_messages = base_messages.copy()
    few_shot_messages.append(message_template('user',
                                              '''请提供与"programming"类似的词。

                                              请以以下JSON格式回复:
                                              ```json
                                              {
                                                "similar_words": ["coding", "development", ...]
                                              }
                                              ```
                                              '''))

    few_shot_response = chat_single(few_shot_messages, mode="json_few_shot",
                                    verbose=True)
    print(f"处理后的响应:\n{few_shot_response}\n")


if __name__ == "__main__":
    run_examples()