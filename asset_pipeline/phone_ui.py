"""Phone UI art (lock screen + notification banner) as SVG.

Text is real Devanagari rendered by resvg (rustybuzz shaping), not
pre-rendered pictures of text, so message copy can change without redrawing.
UI size is 440x800, matching the phone-screen quad's ~0.55 aspect in the
character art.
"""
UW, UH = 440, 800
FONT = "Kohinoor Devanagari, Devanagari Sangam MN, sans-serif"


def lockscreen(time_text="2:47", date_text="शनिवार, 19 सितंबर"):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{UW}" height="{UH}" viewBox="0 0 {UW} {UH}">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b1a33"/><stop offset="1" stop-color="#1c3f6b"/></linearGradient></defs>
<rect width="{UW}" height="{UH}" fill="url(#g)"/>
<text x="{UW/2}" y="200" font-family="{FONT}" font-size="132" font-weight="300" fill="#eaf3ff" text-anchor="middle">{time_text}</text>
<text x="{UW/2}" y="252" font-family="{FONT}" font-size="30" fill="#b8cbe6" text-anchor="middle">{date_text}</text>
<rect x="{UW/2-70}" y="{UH-26}" width="140" height="6" rx="3" fill="#cfe0f7" opacity="0.7"/>
</svg>'''


def banner(title="अज्ञात नंबर", body="एक ज़रूरी बात करनी है…", when="अभी"):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{UW-36}" height="150" viewBox="0 0 {UW-36} 150">
<rect width="{UW-36}" height="150" rx="30" fill="#f5f8fc" opacity="0.96"/>
<rect x="20" y="22" width="64" height="64" rx="16" fill="#2fb44f"/>
<path d="M36,42 h32 a6,6 0 0 1 6,6 v14 a6,6 0 0 1 -6,6 h-16 l-10,9 v-9 h-6 a6,6 0 0 1 -6,-6 v-14 a6,6 0 0 1 6,-6 z" fill="#fff"/>
<text x="102" y="52" font-family="{FONT}" font-size="30" font-weight="700" fill="#111a28">{title}</text>
<text x="{UW-36-22}" y="50" font-family="{FONT}" font-size="22" fill="#6b7788" text-anchor="end">{when}</text>
<text x="102" y="96" font-family="{FONT}" font-size="28" fill="#2a3444">{body}</text>
<text x="102" y="132" font-family="{FONT}" font-size="22" fill="#6b7788">संदेश</text>
</svg>'''
