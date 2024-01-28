#

以下 D:\Apps\steamcmd にインストールした場合の例です。

D:\Apps\steamcmd\steamapps\common\PalServer\Pal\Saved\Config\WindowsServer\PalWorldSettings.ini の
RCONEnabled=False の部分を RCONEnabled=True に変更。


yushimo.ini を以下のように変更してください。

```
[SETTINGS]
token=
webhook_url=
LOOP_SEC=30
RESTART_MEMORY_USAGE_THRESHOLD=40 # 再起動するメモリ使用率の閾値 (%)
RCON_HOST=localhost
RCON_PORT=25575
RCON_PASSWORD= # PalWorldSettings.ini の AdminPassword と同じ
GRACEFUL_SHUTDOWN_TIME=10 # シャットダウンのまでの猶予時間 (秒)
STEAM_CMD_PATH=D:\Apps\steamcmd # steamcmd があるディレクトリのパス
```
RESTART_MEMORY_USAGE_THRESHOLD, RCON_PASSWORD, GRACEFUL_SHUTDOWN_TIME, STEAM_CMD_PATH は適宜変更してください。
RESTART_MEMORY_USAGE_THRESHOLD, GRACEFUL_SHUTDOWN_TIME を低い値で試してみて、大丈夫そうなら上げてください。
RESTART_MEMORY_USAGE_THRESHOLD=70, GRACEFUL_SHUTDOWN_TIME=300 くらいが良いかもしれません。

## 実行
実行前にコマンドプロンプトで `pip install -U mcrcon` を実行してください。
以降は `python3 yushimo.py` を実行してください。
