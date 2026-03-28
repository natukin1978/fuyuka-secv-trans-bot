import asyncio
import json
import logging
import os
import random
import sys

import httpx
import langdetect

import global_value as g
from config_helper import read_config
from logging_setup import setup_app_logging

g.app_name = "fuyuka_secv_trans_bot"
g.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
g.config = read_config()

# ロガーの設定
setup_app_logging(g.config["logLevel"], log_file_path=f"{g.app_name}.log")
logger = logging.getLogger(__name__)

from text_helper import read_text_set
from websocket_helper import websocket_listen_forever

g.set_exclude_id = read_text_set("exclude_id.txt")
g.websocket_stream_live = None


def get_random_value() -> str:
    service = g.config["translate"]["service"]
    if service == "deepL":
        values = g.config["deepL"]["apiKey"]
    if service == "translate_gas":
        values = g.config["translate_gas"]["url"]
    i = random.randrange(len(values))
    return values[i]


async def translate_deepL(text: str, target: str) -> str:
    headers = {"Authorization": f"DeepL-Auth-Key " + get_random_value()}
    data = {
        "text": text,
        "target_lang": target,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                g.config["deepL"]["endpoint"], headers=headers, data=data
            )
            # エラーがあれば例外を発生させる
            response.raise_for_status()
            # レスポンスから翻訳結果を取得
            response_json = response.json()
            translation = response_json["translations"][0]["text"]
            return translation
    except httpx.HTTPStatusError as e:
        return f"HTTPエラーが発生しました: {e}"
    except Exception as e:
        return f"予期しないエラーが発生しました: {e}"


async def translate_gas(text: str, target: str) -> str:
    try:
        params = {
            "text": text,
            "target": target,
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(
                get_random_value(), params=params, follow_redirects=True
            )
            # エラーがあれば例外を発生させる
            response.raise_for_status()
            # レスポンスから翻訳結果を取得
            response_json = response.json()
            return response_json["text"]
    except Exception as e:
        print(e)
        return ""


async def translate(text: str, target: str) -> str:
    service = g.config["translate"]["service"]
    if service == "deepL":
        return await translate_deepL(text, target)
    if service == "translate_gas":
        return await translate_gas(text, target)
    return ""


async def main():
    def get_fuyukaApi_baseUrl() -> str:
        conf_fa = g.config["fuyukaApi"]
        if not conf_fa:
            return ""
        return conf_fa["baseUrl"]

    def is_enable_bot(name: str) -> bool:
        return name in g.config["stream"]["enableBots"]

    async def recv_fuyuka_response(message: str) -> None:
        try:
            json_data = json.loads(message)
            if "response" in json_data:
                # レスポンス付きなら翻訳しない
                return

            if not is_enable_bot(json_data["id"]):
                return

            data = json_data["request"]
            id = data["id"]
            displayName = data["displayName"]
            text = data["content"]

            if id in g.set_exclude_id:
                # 無視するID
                return

            if not text:
                return

            result_langdetect = langdetect.detect(text)
            if result_langdetect == g.config["translate"]["target"]:
                # 母国語と同じ
                return

            translated_text = await translate(text, g.config["translate"]["target"])
            if not translated_text:
                translated_text = text

            print(f"\n{displayName} ({id}):\n{text}\n{translated_text}")

        except json.JSONDecodeError:
            pass

    fuyukaApi_baseUrl = get_fuyukaApi_baseUrl()
    if fuyukaApi_baseUrl:
        websocket_uri = f"{fuyukaApi_baseUrl}/chat/{g.app_name}"
        asyncio.create_task(
            websocket_listen_forever(websocket_uri, recv_fuyuka_response)
        )

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(main())
