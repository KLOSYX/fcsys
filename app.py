from __future__ import annotations

import base64
import json
from io import BytesIO
from typing import Any

import gradio as gr
from PIL import Image
from pyrootutils import setup_root

from config import Config
from fact_checker import get_fact_checker_agent
from retriever import RETRIEVER_LIST
from tools import get_summarizer_chain
from tools import TOOL_LIST

root = setup_root('.', pythonpath=True, dotenv=True)
config = Config()

tool_map = {x.name: x for x in TOOL_LIST}
retriever_map = {x.name: x for x in RETRIEVER_LIST}


def list_to_markdown(lst):
    markdown = ''
    for item in lst:
        markdown += f'- {item}\n'
    return markdown


def inference(raw_image: Any, claim: str):
    if not raw_image or not claim:
        raise ValueError('Image and text should be both provided.')
    tmp_dir = root / '.temp'
    if not tmp_dir.exists():
        tmp_dir.mkdir(parents=True)
    buffer = BytesIO()
    raw_image.save(buffer, format='JPEG')
    image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
    with open(tmp_dir / 'tweet_content.json', 'w') as f:
        f.write(
            json.dumps(
                {
                    'tweet_text': claim,
                    'tweet_image': image_data,
                }, ensure_ascii=False,
            ),
        )
    all_tools = [tool_map[x] for x in selected_tools] + \
                [retriever_map[x] for x in selected_retrievers]
    agent = get_fact_checker_agent(all_tools)
    partial_message = ''
    async for chunk in agent.astream_log(
            {
                'tweet_text': claim,
                'tweet_image_path': str(tmp_dir / 'tweet_content.json'),
            },
    ):
        for op in chunk.ops:
            if op['path'].startswith('/logs/') and op['path'].endswith(
                    '/streamed_output_str/-',
            ):
                # because we chose to only include LLMs, these are LLM tokens
                partial_message += op['value']
            if partial_message.endswith('```'):
                partial_message += '\n'
            yield partial_message
        # partial_message = partial_message + \
        #                   '\n'.join([str(msg.content) for msg in chunk['messages']]) + '\n'
        # yield partial_message
    partial_message += '\n\n---\n\n'
    summarizer = get_summarizer_chain()
    async for chunk in summarizer.astream(
        {
            'claim_text': claim,
            'history': partial_message,
        },
    ):
        partial_message += chunk.content
        yield partial_message


if __name__ == '__main__':
    inputs = [
        gr.Image(type='pil', interactive=True, label='图像'),
        gr.Textbox(lines=2, label='文本', interactive=True),
        gr.Checkboxgroup(
            list(tool_map.keys()), value=list(
                tool_map.keys(),
            ), label='工具选择',
        ),
        gr.Checkboxgroup(
            list(retriever_map.keys()), value=list(
                retriever_map.keys(),
            ), label='知识库选择',
        ),
    ]
    outputs = gr.Markdown(label='输出', sanitize_html=False)

    title = '多模态失序信息检测原型系统'
    description = '该系统提供一个基于大型语言模型(LLM)的代理，用于通过分析图像和文本内容来验证多模态社交媒体信息的真实性。\
    系统接受文本和图像作为输入，并可以灵活组合不同的工具/知识库。 系统将输出真实性判断以及事实核查信息。'
    article = '多模态失序信息检测原型系统'

    gr.Interface(
        inference, inputs, outputs, title=title,
        description=description, article=article,
    ).queue().launch(server_name='0.0.0.0', server_port=7860, ssl_verify=False)
