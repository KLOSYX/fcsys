from __future__ import annotations

import json
from pathlib import Path
from typing import Type
from urllib.parse import urljoin

import requests
from langchain.tools import BaseTool
from pydantic import BaseModel
from pydantic import Field
from pyrootutils import setup_root

from config import Config

config = Config()
root = setup_root('.')

template = """"请简要描述一下图像的内容以及图像中的文本信息。"""


def get_vl_result(image: str) -> str:
    # 构造请求参数
    params = {'image': image, 'text': template}
    # 发送POST请求
    response = requests.post(
        urljoin(config.vl_server_addr, '/vl'), data=params,
    )
    # 获取响应结果
    result = response.text
    return result


def load_tweet_content(image_path: str) -> dict:
    with open(Path(image_path)) as f:
        tweet_content = json.loads(f.read())
    return tweet_content


class ImageScheme(BaseModel):
    image_path: str = Field(
        description='Should be the path of tweet image.',
        default=str(root / '.temp' / 'tweet_content.json'),
    )


class ImageComprehendingTool(BaseTool):
    name = 'image_comprehending_tool'
    description = (
        'Use this tool to obtain text descriptions of tweet image content'
        'use parameter `image_path` as input'
    )
    args_schema: type[ImageScheme] = ImageScheme

    def _run(self, image_path: str) -> str:
        """use tweet summary as input. could be in English and Chinese."""
        tweet_content = load_tweet_content(image_path)
        return get_vl_result(tweet_content['tweet_image']) + '\n'

    async def _arun(self, image_path: str) -> str:
        tweet_content = load_tweet_content(image_path)
        return get_vl_result(tweet_content['tweet_image']) + '\n'
