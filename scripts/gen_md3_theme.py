#!/usr/bin/env python
"""从源色生成 MD3 Expressive 皮肤 CSS。

用法：
    .venv/Scripts/python scripts/gen_md3_theme.py          # 用默认源色
    .venv/Scripts/python scripts/gen_md3_theme.py 0xff39ffcc

输出：src/stylesheets/md3-expressive.css
色板由 material-color-utilities 的 HCT 算法推导，不依赖任何 CDN。
"""

import sys
from pathlib import Path

from material_color_utilities import Hct, theme_from_argb_color

DEFAULT_SRC = 0xFF39FFCC
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "stylesheets" / "md3-expressive.css"

ROLES = [
    "primary", "on_primary", "primary_container", "on_primary_container",
    "secondary", "on_secondary", "secondary_container", "on_secondary_container",
    "tertiary", "on_tertiary", "tertiary_container", "on_tertiary_container",
    "error", "on_error", "error_container", "on_error_container",
    "surface", "on_surface", "surface_variant", "on_surface_variant",
    "surface_container_lowest", "surface_container_low", "surface_container",
    "surface_container_high", "surface_container_highest", "surface_dim", "surface_bright",
    "outline", "outline_variant", "inverse_surface", "inverse_on_surface", "inverse_primary",
    "shadow", "scrim", "surface_tint",
]


def to_argb(color):
    """接受 Hct / int(ARGB) / '#rrggbb' 三种形态。"""
    if isinstance(color, Hct):
        return int(color.argb)
    if isinstance(color, str):
        return int(color.lstrip("#"), 16)
    return int(color)


def hx(color):
    return "#%06x" % (to_argb(color) & 0xFFFFFF)


def rgba(color, alpha):
    v = to_argb(color) & 0xFFFFFF
    return "rgba(%d,%d,%d,%.3g)" % ((v >> 16) & 255, (v >> 8) & 255, v & 255, alpha)


def tokens(scheme, extra):
    lines = []
    for role in ROLES:
        value = getattr(scheme, role, None)
        if value is not None:
            lines.append("  --md-sys-color-%s: %s;" % (role.replace("_", "-"), hx(value)))
    for name, value in extra.items():
        lines.append("  --md-ref-%s: %s;" % (name, value))
    return "\n".join(lines)


def block(scheme, dark):
    """生成一个 color-scheme 块的内容。dark 只影响主色取哪一档。"""
    palette = scheme.primary_palette
    tone = lambda t: hx(palette.get(t))
    extra = {
        "primary-20": tone(20), "primary-30": tone(30), "primary-40": tone(40),
        "primary-70": tone(70), "primary-85": tone(85), "primary-90": tone(90),
        "primary-100": tone(100),
        "tertiary-40": hx(scheme.tertiary_palette.get(40)),
        "tertiary-90": hx(scheme.tertiary_palette.get(90)),
    }
    surface = scheme.surface
    on_surface = scheme.on_surface
    shadow = (
        "0 1px 2px rgba(0,0,0,.3), 0 1px 3px 1px rgba(0,0,0,.15)"
        if dark else
        "0 1px 2px rgba(0,0,0,.05), 0 1px 3px 1px rgba(0,0,0,.04)"
    )
    shadow2 = (
        "0 1px 2px rgba(0,0,0,.3), 0 2px 6px 2px rgba(0,0,0,.15)"
        if dark else
        "0 1px 2px rgba(0,0,0,.08), 0 2px 6px 2px rgba(0,0,0,.06)"
    )
    shadow3 = (
        "0 4px 8px 3px rgba(0,0,0,.3), 0 1px 3px rgba(0,0,0,.3)"
        if dark else
        "0 4px 8px 3px rgba(0,0,0,.08), 0 1px 3px rgba(0,0,0,.1)"
    )
    link = "var(--md-sys-color-primary)"
    low = "var(--md-sys-color-surface-container-lowest)" if dark else "var(--md-sys-color-surface)"

    return """%s

  /* 与 Material 变量对接 */
  --md-primary-fg-color: var(--md-sys-color-primary);
  --md-primary-fg-color--light: var(--md-ref-primary-90);
  --md-primary-fg-color--dark: var(--md-ref-primary-30);
  --md-primary-bg-color: var(--md-sys-color-on-primary);
  --md-primary-bg-color--light: %s;
  --md-accent-fg-color: var(--md-sys-color-tertiary);
  --md-accent-fg-color--transparent: %s;
  --md-accent-bg-color: var(--md-sys-color-on-tertiary);
  --md-accent-bg-color--light: %s;

  --md-default-fg-color: var(--md-sys-color-on-surface);
  --md-default-fg-color--light: var(--md-sys-color-on-surface-variant);
  --md-default-fg-color--lighter: %s;
  --md-default-fg-color--lightest: %s;
  --md-default-bg-color: var(--md-sys-color-surface);
  --md-default-bg-color--light: %s;
  --md-default-bg-color--lighter: %s;
  --md-default-bg-color--lightest: %s;

  --md-typeset-a-color: %s;
  --md-typeset-mark-color: %s;
  --md-typeset-kbd-color: var(--md-sys-color-surface-container-high);
  --md-typeset-kbd-accent-color: %s;
  --md-typeset-kbd-border-color: var(--md-sys-color-outline-variant);
  --md-typeset-table-color: var(--md-sys-color-outline-variant);
  --md-typeset-table-color--light: %s;

  --md-code-bg-color: var(--md-sys-color-surface-container-low);
  --md-code-fg-color: var(--md-sys-color-on-surface);

  --md-footer-bg-color: var(--md-sys-color-surface-container);
  --md-footer-bg-color--dark: var(--md-sys-color-surface-container-high);
  --md-footer-fg-color: var(--md-sys-color-on-surface-variant);
  --md-footer-fg-color--light: var(--md-sys-color-on-surface-variant);
  --md-footer-fg-color--lighter: var(--md-sys-color-on-surface-variant);

  --md-shadow-z1: %s;
  --md-shadow-z2: %s;
  --md-shadow-z3: %s;""" % (
        tokens(scheme, extra),
        rgba(scheme.on_primary, .7), rgba(scheme.tertiary, .1), rgba(scheme.on_tertiary, .7),
        rgba(on_surface, .38), rgba(on_surface, .12),
        rgba(surface, .7), rgba(surface, .3), rgba(surface, .12),
        link, rgba(scheme.primary, .4), low, rgba(on_surface, .05),
        shadow, shadow2, shadow3,
    )


COMPONENTS = """

/* ============================================================ 组件层 */

/* 顶栏：MD3 top app bar —— surface 色 + 分割线，不用阴影 */
.md-header {
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface);
  box-shadow: none;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}
.md-header__topic,
.md-header__title,
.md-header__button,
.md-header__source,
.md-header__ellipsis {
  color: var(--md-sys-color-on-surface);
}
.md-header__button:hover { opacity: .8; }
.md-header--shadow { box-shadow: none; }

/* 搜索框：pill */
.md-search__form {
  background-color: var(--md-sys-color-surface-container-high);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md3-corner-full);
  color: var(--md-sys-color-on-surface-variant);
}
.md-search__form:hover { background-color: var(--md-sys-color-surface-container-highest); }
.md-search__input::placeholder,
.md-search__icon { color: var(--md-sys-color-on-surface-variant); }
[data-md-toggle="search"]:checked ~ .md-header .md-search__form {
  background-color: var(--md-sys-color-surface-container-high);
  border-radius: var(--md3-corner-full);
}

/* 侧边导航：选中项做成 pill */
.md-nav__link {
  border-radius: var(--md3-corner-full);
  padding: .25rem .6rem;
  transition: background-color .15s var(--md3-ease-standard);
}
.md-nav__link:hover { background-color: var(--md-sys-color-surface-container-high); }
.md-nav__link--active,
.md-nav__item--active > .md-nav__link {
  background-color: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
  font-weight: 600;
}
.md-nav__link--active:hover { background-color: var(--md-sys-color-secondary-container); }
.md-nav--primary .md-nav__title {
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface);
}

/* 右侧目录：选中项不带底色 */
.md-nav--secondary .md-nav__link--active {
  background-color: transparent;
  color: var(--md-sys-color-primary);
}

/* 代码块：大圆角 + 容器色 */
.md-typeset pre > code {
  border-radius: 0;
  background-color: transparent;
}
.md-typeset .highlight,
.md-typeset pre,
.md-typeset .highlighttable {
  border-radius: var(--md3-corner-lg);
  overflow: hidden;
}
.md-typeset code {
  border-radius: var(--md3-corner-sm);
  background-color: var(--md-sys-color-surface-container-high);
}
.md-typeset pre > code,
.md-typeset .highlight > pre > code { background-color: transparent; }

/* 提示块 */
.md-typeset .admonition,
.md-typeset details {
  border-radius: var(--md3-corner-lg);
  border-width: 0;
  border-left-width: 2px;
  box-shadow: none;
  background-color: var(--md-sys-color-surface-container-low);
}
.md-typeset .admonition-title,
.md-typeset summary { border-radius: var(--md3-corner-lg) var(--md3-corner-lg) 0 0; }

/* 表格 */
.md-typeset table:not([class]) {
  border-radius: var(--md3-corner-md);
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant);
  box-shadow: none;
}
.md-typeset table:not([class]) th {
  background-color: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
}

/* 按钮：pill + 轻微浮起 */
.md-typeset .md-button {
  border-radius: var(--md3-corner-full);
  padding: .5rem 1.25rem;
  border-width: 1px;
  font-weight: 600;
  transition: box-shadow .2s var(--md3-ease-standard),
              background-color .2s var(--md3-ease-standard),
              transform .2s var(--md3-ease-spring);
}
.md-typeset .md-button--primary {
  background-color: var(--md-ref-primary-90);
  border-color: transparent;
  color: var(--md-ref-primary-20);
}
.md-typeset .md-button--primary:hover {
  box-shadow: var(--md-shadow-z2);
  transform: translateY(-1px);
}

/* 卡片 */
.md-typeset .grid.cards > ul > li {
  border-radius: var(--md3-corner-xl);
  background-color: var(--md-sys-color-surface-container-low);
  border: 1px solid var(--md-sys-color-outline-variant);
  transition: background-color .2s var(--md3-ease-standard),
              box-shadow .2s var(--md3-ease-standard),
              transform .2s var(--md3-ease-spring);
}
.md-typeset .grid.cards > ul > li:hover {
  background-color: var(--md-sys-color-surface-container-high);
  box-shadow: var(--md-shadow-z2);
  transform: translateY(-2px);
}

/* 标签、页脚 */
.md-typeset .md-tag { border-radius: var(--md3-corner-full); }
.md-footer { border-top: 1px solid var(--md-sys-color-outline-variant); }
.md-footer-meta { background-color: var(--md-sys-color-surface-container-high); }

/* 博客列表条目 */
.md-post--excerpt {
  border-radius: var(--md3-corner-lg);
  background-color: var(--md-sys-color-surface-container-low);
}
"""

HEADER = """/* =========================================================================
   MD3 Expressive 皮肤 —— 自动生成，请勿手改
   源色 %s，由 material-color-utilities 的 HCT 算法推导出完整 tonal palette
   重新生成：.venv/Scripts/python scripts/gen_md3_theme.py <0xAARRGGBB>
   ========================================================================= */

:root {
  /* MD3 shape scale */
  --md3-corner-xs: 4px;
  --md3-corner-sm: 8px;
  --md3-corner-md: 12px;
  --md3-corner-lg: 16px;
  --md3-corner-xl: 28px;
  --md3-corner-full: 999px;
  /* MD3 motion */
  --md3-ease-emphasized: cubic-bezier(.2, 0, 0, 1);
  --md3-ease-standard: cubic-bezier(.2, 0, 0, 1);
  --md3-ease-spring: cubic-bezier(.34, 1.3, .64, 1);
}
"""


def main():
    src = int(sys.argv[1], 16) if len(sys.argv) > 1 else DEFAULT_SRC
    theme = theme_from_argb_color(src)
    light, dark = theme.schemes.light, theme.schemes.dark

    css = (
        HEADER % ("#%06x" % (src & 0xFFFFFF))
        + '\n/* ---------------------------------------------------------- 浅色 */\n'
        + '[data-md-color-scheme="default"] {\n'
        + block(light, dark=False) + "\n}\n"
        + '\n/* ---------------------------------------------------------- 深色 */\n'
        + '[data-md-color-scheme="slate"] {\n'
        + block(dark, dark=True) + "\n}\n"
        + COMPONENTS
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(css, encoding="utf-8", newline="\n")

    p = light.primary_palette
    print("wrote %s (%d bytes)" % (OUT, len(css)))
    print("light: primary=%s container=%s surface=%s link=%s"
          % (hx(light.primary), hx(light.primary_container), hx(light.surface), hx(p.get(40))))
    print("dark : primary=%s container=%s surface=%s"
          % (hx(dark.primary), hx(dark.primary_container), hx(dark.surface)))


if __name__ == "__main__":
    main()
