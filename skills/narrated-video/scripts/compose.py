# Build the HyperFrames composition for a narrated video. A per-video script (see examples/) imports this module:
#   import compose as C
#   T = C.timing({'intro': 0.0, 'search': cu.onset(14.3) - 0.3, ...}, total=C.f30(last_word + 1.8))
#   secs = [C.backdrop(T, 'bg.png'), C.scene('intro', T, C.canvas('intro', C.camera('in-o', 'in-i', ['home.png'])),
#           C.label('lb-in', 'A quick tour')), C.end_card(T, 'og.png'), C.cam_slot(T)]
#   C.write('comp', T, secs, consts=dict(A=A), choreo=CHOREO, assets='assets', title='Launch video')
# The choreography (CHOREO) is JavaScript using the template's helpers: setFrame, moveTo, drift, cAt/cShow/cMove/
# cClick, typeFrames, showFrame, show/hide/fadeIn, label, out. See references/composition.md.
import json, math, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.normpath(os.path.join(HERE, '..', 'templates'))
FPS = 30
LAYOUTS = {
    # 16:9 1080p: the 1200x792 window at 1.2x on the left, the webcam bubble in its own column, bottom-aligned with it
    '1080p': dict(W=1920, H=1080, U=1.2, WIN_X=64, WIN_Y=65, WIN_S=1.2, LABEL_X=784, CAM_X=1552, CAM_Y=695, CAM_D=320),
    # 16:10 1440x900
    '1440x900': dict(W=1440, H=900, U=1, WIN_X=56, WIN_Y=94, WIN_S=0.9, LABEL_X=596, CAM_X=1160, CAM_Y=556, CAM_D=250),
}
CURSOR_SVG = ('<svg viewBox="0 0 26 36" width="26" height="36"><path d="M2.5 2.2 L2.5 28.6 L9.2 22.3 L13.6 32.6 L18 30.7 '
              'L13.7 20.6 L22.6 20.6 Z" fill="#111" stroke="#fff" stroke-width="2" stroke-linejoin="round"/></svg>')


def f30(t): return round(t * FPS) / FPS


def timing(starts, total):
    """Scene windows from scene start times. Each scene starts on a frame; its timeline time is that frame's time in
    ms rounded down (so everything set at the scene's start has fired by its first frame), and its visibility window
    begins half a frame earlier, between two frames, so no frame can fall in no scene (the backdrop flashes through)
    or in two (a doubled window shadow). Videos share their scene's window."""
    order = sorted(starts, key=starts.get)
    F = {k: round(starts[k] * FPS) for k in order}
    S = {k: math.floor(F[k] / FPS * 1000 + 1e-6) / 1000 for k in order}
    DUR = {k: round((S[order[i + 1]] if i + 1 < len(order) else total) - S[k], 3) for i, k in enumerate(order)}
    edge = {k: round(max(0.0, (F[k] - 0.5) / FPS), 4) for k in order}
    edge_end = [edge[order[i + 1]] if i + 1 < len(order) else total for i in range(len(order))]
    WIN = {k: (f'{edge[k]:.4f}', f'{edge_end[i] - edge[k]:.4f}' if i + 1 < len(order) else repr(total - edge[k])) for i, k in enumerate(order)}
    for k in order: print(f'{k:8s} {S[k]:8.3f} +{DUR[k]:6.2f}')
    print('TOTAL', round(total, 3))
    return dict(order=order, F=F, S=S, DUR=DUR, WIN=WIN, TOTAL=total)


def window(url, inner, fade_bg='#fff', content_bg=None):
    cs = f' style="background: {content_bg}"' if content_bg else ''
    return (f'<div class="win"><div class="titlebar"><i></i><i></i><i></i><span class="url">{url}</span></div>\n'
            f'      <div class="content"{cs}>{inner}<div class="fade" style="background: {fade_bg}"></div></div></div>')


def camera(oid, iid, srcs, tall=None, hidden=False):
    """A camera layer over 1440-wide screenshots: one image, or a stack (typing frames, before/after states) whose
    images are id'd iid-0, iid-1, ... and shown with showFrame/typeFrames. The pointer lives on top (iid-cur)."""
    imgs = []
    for n, src in enumerate(srcs):
        cls = ' class="tall"' if tall else ''
        st = f' style="height: {tall}px"' if tall else ''
        imgs.append(f'<img id="{iid}-{n}"{cls} src="assets/{src}" alt=""{st} />')
    stack = ' stack' if len(srcs) > 1 else ''
    style = ' style="opacity: 0"' if hidden else ''
    return (f'<div class="zoom-outer" id="{oid}"{style}><div class="zoom-inner{stack}" id="{iid}">{"".join(imgs)}'
            f'<div class="cur" id="{iid}-cur"><div class="cur-p">{CURSOR_SVG}</div></div></div></div>')


def canvas(k, *layers):
    """The 1440x900 screenshot space inside the window, with the scene's click-pulse overlay above every layer."""
    return ('<div class="canvas1440">' + ''.join(layers) + '<div class="ovl">'
            + ''.join(f'<div class="rip" id="{k}-q{n}"></div>' for n in range(4)) + '</div></div>')


def label(i, text, long=False):
    cls = ' class="long"' if long else ''   # outside the f-string: a backslash in one is a SyntaxError before Python 3.12
    return f'<div class="label" id="{i}"><h2{cls}>{text}</h2></div>'


def scene(k, T, body, labels='', url='app.example.com', fade_bg='#fff', content_bg=None):
    w = T['WIN'][k]
    return (f'  <section class="clip" id="s-{k}" data-start="{w[0]}" data-duration="{w[1]}">\n'
            f'    {window(url, body, fade_bg, content_bg)}\n    {labels}\n  </section>')


def recording(k, T, src, oid, iid, page=False):
    """A screen recording in the window's pane (a clip trimmed to the scene with ffmpeg, keyframes every 15 frames)."""
    w = T['WIN'][k]
    return (f'<div class="vz-o{" page" if page else ""}" id="{oid}"><div class="vz-i" id="{iid}"><video class="rec" id="{k}-v" '
            f'src="assets/{src}" muted playsinline data-start="{w[0]}" data-duration="{w[1]}"></video></div></div>')


def backdrop(T, src=None):
    inner = f'<img class="world" id="world" src="assets/{src}" alt="" />' if src else '<div class="world grad" id="world"></div>'
    return f'  <section class="clip" id="s-bg" data-start="0" data-duration="{T["TOTAL"]}">\n    {inner}\n  </section>'


def end_card(T, src, k='end'):
    w = T['WIN'][k]
    return (f'  <section class="clip" id="s-{k}" data-start="{w[0]}" data-duration="{w[1]}">\n'
            f'    <div class="og" id="{k}-og"><img src="assets/{src}" alt="" /></div>\n  </section>')


def cam_slot(T):
    return (f'  <section class="clip" id="s-cam" data-start="0" data-duration="{T["TOTAL"]}" style="background: transparent">\n'
            f'    <div class="cam-slot"></div>\n  </section>')


def write(project, T, sections, consts, choreo, assets='assets', layout='1080p', title='Narrated video', extra_css='', window_until=None):
    """Write <project>/index.html, layout.json and scenes.json; link the assets folder; add fonts and HyperFrames files.
    window_until: time the app window leaves the screen (check.py looks for it on every frame before that)."""
    L = LAYOUTS[layout] if isinstance(layout, str) else layout
    times = [f'  const S = {json.dumps(T["S"])};', f'  const DUR = {json.dumps(T["DUR"])};', f'  const TOTAL = {T["TOTAL"]};',
             '  const E = (k) => S[k] + DUR[k];'] + [f'  const {k} = {json.dumps(v)};' for k, v in consts.items()]
    html = open(os.path.join(TEMPLATES, 'composition.html')).read()
    for k, v in dict(TITLE=title, TOTAL=T['TOTAL'], SECTIONS='\n\n'.join(sections), TIMES='\n'.join(times), CHOREO=choreo, EXTRA_CSS=extra_css, **L).items():
        html = html.replace(f'%%{k}%%', str(v))
    assert '%%' not in html, 'unfilled template field'
    assets = os.path.abspath(assets)
    for part in html.split('src="assets/')[1:]:
        f = part.split('"')[0]
        assert os.path.exists(os.path.join(assets, f)), f'missing asset: {f}'
    os.makedirs(project, exist_ok=True)
    link = os.path.join(project, 'assets')
    if os.path.islink(link) and os.path.realpath(link) != os.path.realpath(assets): os.remove(link)
    if not os.path.exists(link): os.symlink(assets, link)
    shutil.copytree(os.path.join(TEMPLATES, 'fonts'), os.path.join(project, 'fonts'), dirs_exist_ok=True)
    for f in ('hyperframes.json', 'package.json'):
        if not os.path.exists(os.path.join(project, f)): shutil.copy(os.path.join(TEMPLATES, f), project)
    open(os.path.join(project, 'index.html'), 'w').write(html)
    json.dump(L, open(os.path.join(project, 'layout.json'), 'w'))
    last = T['order'][-1]
    json.dump(dict(S=T['S'], DUR=T['DUR'], TOTAL=T['TOTAL'], F=T['F'], WIN=T['WIN'], order=T['order'], A=consts.get('A', {}),
                   window_until=window_until if window_until is not None else T['S'][last] - 0.8),
              open(os.path.join(project, 'scenes.json'), 'w'))
    print(f'wrote {project}/index.html ({L["W"]}x{L["H"]}, {T["TOTAL"]} s)')
