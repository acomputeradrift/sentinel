import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GROUP_JS = ROOT / "src" / "sentinel" / "ui" / "testing" / "sentinel_group_pass_embed.js"
RENDER = ROOT / "src" / "sentinel" / "generation" / "render_core.py"


class GroupPassMarqueeViewportTest(unittest.TestCase):
    def test_marquee_query_skips_device_page_viewport_wraps(self):
        js = GROUP_JS.read_text(encoding="utf-8")
        render = RENDER.read_text(encoding="utf-8")
        self.assertIn('wrapSelector: ".device-page .btn-wrap, .vp-popup-vcontent .btn-wrap.vp-btn"', render)
        self.assertIn(".btn-wrap:not(.vp-btn)", js)
        self.assertIn("isInsideDeviceViewportBox", js)
        self.assertIn("isSelectableTarget: isSelectableTarget", js)

    def test_selectable_target_excludes_device_page_viewport_contents(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        script = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8');
function tokenList(names) {
  const set = new Set(String(names || '').split(/\s+/).filter(Boolean));
  return {
    contains: (c) => set.has(c),
    add: (c) => { set.add(c); },
    remove: (c) => { set.delete(c); },
    toggle: (c, on) => { if (on) set.add(c); else set.delete(c); return on; },
  };
}
function makeEl(spec) {
  const el = {
    classList: tokenList(spec.className),
    hidden: !!spec.hidden,
    parentNode: spec.parent || null,
    attrs: Object.assign({}, spec.attrs || {}),
    rect: spec.rect || {left: 0, top: 0, width: 10, height: 10},
    kids: spec.kids || [],
    getAttribute: function (k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? String(this.attrs[k]) : null; },
    hasAttribute: function (k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); },
    getBoundingClientRect: function () {
      const r = this.rect;
      return {left: r.left, top: r.top, width: r.width, height: r.height, right: r.left + r.width, bottom: r.top + r.height};
    },
    closest: function (sel) {
      let n = this;
      while (n) {
        if (matches(n, sel)) return n;
        n = n.parentNode;
      }
      return null;
    },
    querySelectorAll: function (sel) {
      const out = [];
      (function walk(node) {
        (node.kids || []).forEach(function (child) {
          if (matches(child, sel)) out.push(child);
          walk(child);
        });
      })(this);
      return out;
    },
    querySelector: function (sel) { return this.querySelectorAll(sel)[0] || null; },
  };
  (el.kids || []).forEach(function (k) { k.parentNode = el; });
  return el;
}
function matches(el, sel) {
  if (!el || !sel) return false;
  if (sel.charAt(0) === '#') return el.attrs && el.attrs.id === sel.slice(1);
  const parts = String(sel).split('.').filter(Boolean);
  if (!parts.length) return false;
  return parts.every(function (p) { return el.classList.contains(p); });
}
const pageBtn = makeEl({className: 'btn-wrap', rect: {left: 10, top: 10, width: 80, height: 40}});
const vpChild = makeEl({className: 'btn-wrap vp-btn', attrs: { 'data-vp': '0' }, rect: {left: 30, top: 90, width: 80, height: 40}});
const unmarkedInside = makeEl({className: 'btn-wrap', rect: {left: 40, top: 100, width: 60, height: 30}});
const vpBox = makeEl({className: 'vp-box', rect: {left: 20, top: 80, width: 200, height: 160}});
const page = makeEl({className: 'device-page', kids: [pageBtn, vpChild, unmarkedInside, vpBox]});
const popupBtn = makeEl({className: 'btn-wrap vp-btn', attrs: { 'data-vp': '0' }, rect: {left: 8, top: 8, width: 40, height: 20}});
const popup = makeEl({className: 'vp-popup-vcontent', kids: [popupBtn]});
const body = makeEl({className: ''});
const document = {
  body: body,
  getElementById: function () { return null; },
  querySelector: function () { return null; },
  querySelectorAll: function () { return []; },
  createElement: function () { return makeEl({className: ''}); },
  head: { appendChild: function () {} },
  addEventListener: function () {},
};
global.document = document;
global.window = global;
globalThis.document = document;
eval(src);
const api = globalThis.__sentinelGroupPass;
const out = {
  exported: typeof api.isSelectableTarget === 'function',
  pageBtn: api.isSelectableTarget(pageBtn),
  vpChild: api.isSelectableTarget(vpChild),
  unmarkedInside: api.isSelectableTarget(unmarkedInside),
  popupClosed: api.isSelectableTarget(popupBtn),
};
body.classList.add('viewport-mode');
out.popupOpen = api.isSelectableTarget(popupBtn);
out.vpChildWhileZoom = api.isSelectableTarget(vpChild);
process.stdout.write(JSON.stringify(out));
"""
        proc = subprocess.run(
            [node, "-e", script, str(GROUP_JS)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        body = json.loads(proc.stdout)
        self.assertTrue(body["exported"], "isSelectableTarget must be exported for marquee rules")
        self.assertTrue(body["pageBtn"], "device-page buttons outside viewports stay selectable")
        self.assertFalse(body["vpChild"], "device-page viewport children must not be marquee-selectable")
        self.assertFalse(body["unmarkedInside"], "wraps inside a .vp-box must not be marquee-selectable")
        self.assertFalse(body["popupClosed"], "popup viewport buttons stay unselectable until zoom viewer")
        self.assertTrue(body["popupOpen"], "viewport zoom viewer buttons are selectable")
        self.assertFalse(body["vpChildWhileZoom"], "device-page viewport clones stay unselectable in zoom viewer")


if __name__ == "__main__":
    unittest.main()
