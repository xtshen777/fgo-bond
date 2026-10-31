# FGO 羁绊礼装配装

非官方粉丝工具。选 6 个英灵，自动算出带哪几张羁绊礼装全队羁绊最高（日服数据）。

网址：https://xtshen777.github.io/fgo-bond/

本项目与 TYPE-MOON、FGO PROJECT、Lasengle、Aniplex 及 Fate/Grand Order 官方没有任何关联，也未获得其授权或认可。游戏名称、图片和数据的版权归各自权利人所有。数据和图片来自 [Atlas Academy](https://atlasacademy.io/)。如权利人要求移除内容，请提交 Issue。

## 更新数据

需要 macOS（图片缩放用系统自带的 sips）。

```bash
rm -f .cache/*.json
python3 tools/build.py
```

脚本会重新生成 `index.html`。如果提示缺中文名，把新英灵补到 `tools/build.py` 的 `ZH_NAMES`；新羁绊礼装加到 `EQUIP_IDS`。

页面逻辑和样式在 `tools/template.html`，不要直接改 `index.html`。
