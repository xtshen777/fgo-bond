#!/usr/bin/env python3
"""从 Atlas Academy 拉取日服数据，生成 ../index.html。

用法：python3 tools/build.py [--cache 缓存目录]
图片缩放依赖 macOS 自带的 sips。已下载的文件会复用，要更新数据时删掉缓存里的 json。
"""
import argparse
import base64
import concurrent.futures
import json
import pathlib
import subprocess
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = 'https://api.atlasacademy.io/export'
FILES = {
    'nice_servant_jp.json': f'{API}/JP/nice_servant_lang_en.json',
    'nice_servant_cn.json': f'{API}/CN/nice_servant.json',
    'nice_equip_jp.json': f'{API}/JP/nice_equip_lang_en.json',
    'nice_equip_cn.json': f'{API}/CN/nice_equip.json',
}

# 参与判定的特性；2801200 是「カルデアの者」规则里的所罗门专用特性
TRAITS = {
    'alignmentLawful', 'alignmentChaotic', 'alignmentNeutral', 'alignmentGood', 'alignmentEvil',
    'alignmentBalanced', 'alignmentSummer', 'alignmentMadness', 'alignmentBride', 'genderFemale',
    'hasCostume', 'livingHuman', 'havingAnimalsCharacteristics', 'attributeStar', 'FSNServant',
    'standardClassServant', '2801200',
}

# 常驻的羁绊礼装。只在特定活动有效的不收录。
EQUIP_IDS = [
    1949, 2020, 2052, 2124, 2142, 2209, 2233, 2437, 2509, 2583, 2607, 2701,
    330, 910, 1080, 1121, 1149, 1410, 1565, 1605, 1726,
    1973, 1974, 1975, 1976, 1977, 1978, 1979,
    *range(99, 109), *range(2512, 2533),
]

# 国服未实装英灵的中文名：编号 -> (显示名, 额外搜索词)。新英灵在这里补。
ZH_NAMES = {
    461: ('领主洛格雷斯', ''), 466: ('雅克·德·莫莱', '杰克·德·莫莱'),
    472: ('格蕾·Lily(Saber)', '格蕾 Lily'), 470: ('终末的Archer', '乌尔德 乌尔兹'),
    480: ('小野小町', ''), 473: ('格蕾·Lily(Lancer)', '格蕾 Lily'),
    465: ('德墨忒尔', '得墨忒耳'), 468: ('希波吕忒', ''), 478: ('莉莉丝', ''),
    483: ('玉藻艾莉亚', '玉藻亚里亚 玉藻阿莉亚 玉藻 tamamo aria'),
    467: ('普勒拉蒂', '弗朗索瓦·普勒拉蒂'), 462: ('花咲翁', ''), 477: ('比肖内(Caster)', ''),
    463: ('蛇女房', ''), 474: ('哈桑·萨巴赫', '山中老人'), 475: ('红阎魔(Berserker)', '红阎魔'),
    482: ('代达罗斯', ''), 464: ('芙萝拉', ''), 471: ('阿斯卡拉福斯', ''),
    469: ('无地王约翰', '约翰·拉克兰'), 479: ('Kingprotea Alter', '金普罗提亚 Alter'),
    476: ('Kingprotea(MoonCancer)', '金普罗提亚'), 459: ('所罗门(Pretender)', ''),
    481: ('哈贝特洛特', ''),
}

HEAD = '''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="非官方粉丝工具：选 6 个英灵，自动算出带哪几张羁绊礼装全队羁绊最高（日服数据）。">
<style>
:root { padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }
body { margin: 0; }
img { max-width: 100%; }
[hidden] { display: none !important; }
</style>
'''


def download(url, path):
    if path.exists() and path.stat().st_size:
        return
    with urllib.request.urlopen(url, timeout=300) as r:
        path.write_bytes(r.read())


def load(cache, name):
    download(FILES[name], cache / name)
    return json.loads((cache / name).read_text(encoding='utf8'))


def trait_name(t):
    return str(t['id']) if t['id'] == 2801200 else t['name']


def fetch_images(urls, folder):
    folder.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(10) as pool:
        list(pool.map(lambda kv: download(kv[1], folder / f'{kv[0]}.png'), urls.items()))


def shrink(folder, size, fmt, opts=()):
    """把 folder 里的 PNG 缩小，返回 编号 -> data URI。"""
    with tempfile.TemporaryDirectory() as tmp:
        files = sorted(str(p) for p in folder.glob('*.png'))
        subprocess.run(['sips', '-s', 'format', fmt, *opts, '-Z', str(size), *files, '--out', tmp],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        mime = {'jpeg': 'image/jpeg', 'png': 'image/png'}[fmt]
        out = {}
        for p in pathlib.Path(tmp).iterdir():
            out[int(p.stem)] = f'data:{mime};base64,' + base64.b64encode(p.read_bytes()).decode()
        return out


def build_servants(cache):
    jp = [s for s in load(cache, 'nice_servant_jp.json')
          if s['collectionNo'] > 0 and s['type'] in ('normal', 'heroine')]
    cn = {s['collectionNo']: s for s in load(cache, 'nice_servant_cn.json')}
    out, faces = [], {}
    for s in jp:
        n = s['collectionNo']
        base = {trait_name(t) for t in s['traits']} & TRAITS
        add = s['ascensionAdd'].get('individuality', {})
        alt = set()
        for group in ('ascension', 'costume'):
            for traits in add.get(group, {}).values():
                alt |= ({trait_name(t) for t in traits} & TRAITS) - base
        row = dict(n=n, c=s['className'], r=s['rarity'], zh=cn[n]['name'] if n in cn else '',
                   ja=s['originalName'], en=s['name'], t=sorted(base), a=sorted(alt))
        if n in ZH_NAMES:
            row['zh'], row['k'] = ZH_NAMES[n]
        elif not row['zh']:
            print('缺中文名，请补到 ZH_NAMES：', n, s['originalName'], s['name'])
        out.append(row)
        asc = s['extraAssets']['faces']['ascension']
        faces[n] = asc[max(asc, key=int)]
    return out, faces


def build_equips(cache):
    jp = {e['collectionNo']: e for e in load(cache, 'nice_equip_jp.json')}
    cn = {e['collectionNo']: e for e in load(cache, 'nice_equip_cn.json')}
    out, faces = [], {}
    for n in EQUIP_IDS:
        e = jp[n]
        skills = [x for x in e['skills'] if x.get('condLimitCount') == 4] or e['skills']
        f = next(f for x in skills for f in x['functions'] if f['funcType'] == 'servantFriendshipUp')
        val = f['svals'][0]
        if f.get('overWriteTvalsList'):
            rule = [[trait_name(t) for t in g] for g in f['overWriteTvalsList']]
        else:
            rule = [[trait_name(t)] for t in f['functvals']]
        row = dict(n=n, ja=e['originalName'], zh=cn[n]['name'] if n in cn else '',
                   rate=val.get('RateCount', 0) / 10, rule=rule)
        if 'AddCount' in val:
            row['flat'] = val['AddCount']
        if f['funcTargetType'] == 'self':
            row['self'] = 1
        out.append(row)
        faces[n] = next(iter(e['extraAssets']['faces']['equip'].values()))
    return out, faces


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default=str(ROOT / '.cache'))
    args = ap.parse_args()
    cache = pathlib.Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    servants, s_urls = build_servants(cache)
    equips, e_urls = build_equips(cache)
    fetch_images(s_urls, cache / 'faces')
    fetch_images(e_urls, cache / 'equips')
    s_img = shrink(cache / 'faces', 96, 'jpeg', ('-s', 'formatOptions', '72'))
    e_img = shrink(cache / 'equips', 72, 'png')
    for s in servants:
        s['f'] = s_img[s['n']]
    for c in equips:
        c['img'] = e_img[c['n']]

    data = json.dumps(dict(s=servants, ce=equips), ensure_ascii=False, separators=(',', ':'))
    page = (ROOT / 'tools' / 'template.html').read_text(encoding='utf8').replace('/*DATA*/', data)
    head, body = page.split('<div class="wrap">', 1)
    (ROOT / 'index.html').write_text(f'{HEAD}{head}</head>\n<body>\n<div class="wrap">{body}</body>\n</html>\n', encoding='utf8')
    print('英灵', len(servants), '礼装', len(equips), 'index.html', (ROOT / 'index.html').stat().st_size)


if __name__ == '__main__':
    main()
