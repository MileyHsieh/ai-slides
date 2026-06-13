import sys
import re
import os

# 解決 Windows 終端機 CP950 編碼不支援 Emoji/特殊字元導致的崩潰問題
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def strip_speaker_notes(slide_text):
    # 1. 移除 HTML 註解 (如 <!-- note: ... --> 或 <!-- 講稿：... -->)
    slide_text = re.sub(r'<!--.*?-->', '', slide_text, flags=re.DOTALL)

    # 2. 移除 Obsidian Callouts (如 > [!note] 講師備忘 ... 及其後續所有以 > 開頭的行)
    lines = slide_text.split('\n')
    cleaned_lines = []
    in_note_callout = False

    for line in lines:
        stripped = line.strip()
        # 判斷是否為 Callout 的起頭，支援 [!note], [!memo], [!info], [!tip], [!todo], [!summary], [!abstract] 等
        if stripped.startswith('>') and re.search(r'^>\s*\[!(note|memo|info|tip|todo|summary|abstract|warning|attention|caution|danger|error|bug|quote)\]', stripped, re.IGNORECASE):
            in_note_callout = True
            continue  # 跳過起頭行

        if in_note_callout:
            if stripped.startswith('>'):
                continue  # 跳過後續所有以 > 開頭的行
            else:
                in_note_callout = False  # 遇到非 > 開頭的行，說明 Callout 結束

        # 3. 另外支援簡單的「講稿：」或「Note:」獨立段落 (非列表)
        if stripped.startswith('講稿：') or stripped.startswith('講師備忘：') or stripped.startswith('Note:') or stripped.startswith('Notes:'):
            continue  # 直接跳過該行

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines).strip()

def parse_markdown_slides(md_path):
    if not os.path.exists(md_path):
        print(f"找不到 Markdown 檔案: {md_path}")
        return []

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 以 --- 作為投影片換頁分隔符
    # 移除開頭和結尾的空白
    raw_slides = content.split('\n---\n')

    slides_data = []
    for index, raw_slide in enumerate(raw_slides):
        raw_slide = raw_slide.strip()
        if not raw_slide:
            continue

        # 提取投影片類型，例如 <!-- type: title -->
        type_match = re.search(r'<!--\s*type:\s*(\S+)\s*-->', raw_slide)
        slide_type = type_match.group(1) if type_match else 'bullet-list'

        # 如果是第一個區塊且類型不是 title，則判定為 Obsidian 備課筆記與說明前言，自動跳過
        if index == 0 and slide_type != 'title':
            print("   跳過開頭的備課筆記與說明前言...")
            continue

        # 移除講稿、備忘錄與 HTML 註解
        clean_slide = strip_speaker_notes(raw_slide)

        slides_data.append({
            'index': len(slides_data) + 1,
            'type': slide_type,
            'raw_text': clean_slide
        })

    return slides_data

def build_slide_html(slide, current_theme=""):
    idx = slide['index']
    stype = slide['type']
    text = slide['raw_text']

    # 預設 active 類別給第一張投影片
    active_class = " active-slide" if idx == 1 else ""

    # 提取標題 (# 標題)
    title_match = re.search(r'^#\s+(.*)$', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    # 去除標題後的其餘內文
    body_text = text
    if title_match:
        body_text = text[title_match.end():].strip()

    # 正則表達式處理螢光筆與橘字強調標籤
    # 將 Markdown **強調** 轉換為深橘色重點，將 ==螢光筆== 轉換為淺藍色螢光筆
    # 或支援 Markdown 裡的 <span class="hl-blue">...</span>
    def apply_formatting(t):
        t = re.sub(r'\*\*(.*?)\*\*|__([\s\S]*?)__', r'<span class="emphasis font-bold">\1\2</span>', t)
        t = re.sub(r'==(.*?)==', r'<span class="hl-blue">\1</span>', t)
        return t

    def apply_images(t):
        """將 ![alt](images/xxx) 語法轉換為 HTML img 標籤"""
        t = re.sub(
            r'!\[([^\]]*)\]\(([^\)]+)\)',
            r'<img src="\2" alt="\1" style="max-width:100%; max-height:320px; border-radius:8px; margin: 0.8rem auto; display:block;">',
            t
        )
        return t

    # 0. Theme Title Slide Layout (主題轉場頁)
    if stype == 'theme-title':
        points = re.findall(r'^[*+-]\s+(.*)$', body_text, re.MULTILINE)
        num_points = re.findall(r'^\d+\.\s+(.*)$', body_text, re.MULTILINE)
        list_items = points if points else num_points
        points_html = ""
        for i, pt in enumerate(list_items):
            # 去掉項目文字開頭的「數字. 」前綴（如 "1. 即時互動" → "即時互動"）
            pt_clean = re.sub(r'^\d+\.\s*', '', pt.strip())
            pt_fmt = apply_formatting(pt_clean)
            points_html += f"""
            <div class="theme-point-item">
              <span class="theme-point-num">{i+1}</span>
              <span class="theme-point-text">{pt_fmt}</span>
            </div>"""

        theme_no = "THEME"
        m = re.search(r'主題([一二三四五六七八九十]|[\d]+)', title)
        if m:
            theme_num_map = {"一": "01", "二": "02", "三": "03", "四": "04", "五": "05"}
            t_num = m.group(1)
            if t_num in theme_num_map:
                theme_no = f"THEME {theme_num_map[t_num]}"
            else:
                theme_no = f"THEME {t_num}"

        clean_title = re.sub(r'^主題[一二三四五六七八九十]：\s*', '', title)

        return f"""
      <!-- Slide {idx}: 主題轉場頁 {theme_no} (由 MD 自動編譯) -->
      <section class="slide title-slide theme-title-slide{active_class}" id="slide-{idx}">
        <div class="slide-content center-content">
          <div class="theme-tag">{theme_no}</div>
          <h1 class="slide-title font-giant">{clean_title}</h1>
          <div class="theme-points-list">
            {points_html}
          </div>
        </div>
      </section>
"""

    # 1. Title Slide Layout
    elif stype == 'title':
        subtitle_match = re.search(r'^##\s+(.*)$', body_text, re.MULTILINE)
        subtitle = subtitle_match.group(1).strip() if subtitle_match else ""
        subtitle_html = apply_formatting(subtitle)

        footer_items = re.findall(r'^[*+-]\s+(.*)$', body_text, re.MULTILINE)

        # 決定封面頂部貼標與底部 footer 內容
        tag_text = "佛堂青少年班專屬課堂"
        footer_html = ""

        if len(footer_items) >= 3:
            tag_text = footer_items[0]
            footer_html = f'<span>{footer_items[1]}</span><span>{footer_items[2]}</span>'
        elif len(footer_items) == 2:
            tag_text = footer_items[0]
            footer_html = f'<span>時間：50 分鐘</span><span>{footer_items[1]}</span>'
        elif len(footer_items) == 1:
            tag_text = footer_items[0]
            footer_html = '<span>時間：50 分鐘</span><span>主講人：佛堂講師</span>'
        else:
            footer_html = '<span>時間：50 分鐘</span><span>主講人：佛堂講師</span>'

        return f"""
      <!-- Slide {idx}: 封面 (由 MD 自動編譯) -->
      <section class="slide title-slide{active_class}" id="slide-{idx}">
        <div class="slide-content center-content">
          <div class="tag">{tag_text}</div>
          <h1 class="slide-title font-giant">{title}</h1>
          <p class="slide-subtitle font-large">{subtitle_html}</p>
          <div class="slide-footer">
            {footer_html}
          </div>
        </div>
      </section>
"""

    # 2. Word Cloud Slide Layout
    elif stype == 'word-cloud':
        desc_match = re.search(r'^[*+-]\s+(.*)$', body_text, re.MULTILINE)
        desc = desc_match.group(1).strip() if desc_match else "請拿起手機，掃描左側二維碼回答問題。"
        desc_html = apply_formatting(desc)

        tag_category_html = f'<div class="tag-category">{current_theme}</div>' if current_theme else ""

        return f"""
      <!-- Slide {idx}: 文字雲開場互動 (由 MD 自動編譯) -->
      <section class="slide{active_class}" id="slide-{idx}">
        <div class="slide-content split-layout" style="padding-top: 3.5rem;">
          {tag_category_html}
          <div class="left-col">
            <h2 class="slide-heading" style="font-size: 2.4rem;">{apply_formatting(title)}</h2>
            <p class="slide-desc font-small" style="margin-bottom:1rem;">{desc_html}</p>

            <!-- 掃碼區域 -->
            <div class="qr-box" style="padding: 1rem; gap: 1rem;">
              <img id="presenter-qr" src="" alt="二維碼載入中..." style="width: 100px; height: 100px;">
              <div class="qr-info">
                <p class="font-small font-bold" style="font-size:0.95rem;">📱 手機掃碼或瀏覽連結：</p>
                <code id="presenter-url" style="font-size:0.8rem; padding: 0.3rem 0.6rem; display:block; max-width:260px; overflow-x:auto;">載入中...</code>
              </div>
            </div>

            <!-- 內嵌填寫回答區 -->
            <div class="interactive-form-box" style="margin-top: 0.8rem; padding: 1.2rem; background: var(--bg-color-card); border-radius: var(--radius-sm); border: 2px solid var(--border-color);">
              <h3 class="font-bold" style="font-size: 1.1rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.3rem;">💬 輸入你的答案：</h3>
              <div class="input-group-row" style="display: flex; gap: 0.5rem;">
                <input type="text" id="slide2-answer-input" placeholder="例如：傳遞溫暖 (限8字)" maxlength="8" style="padding: 0.6rem; font-size: 1.1rem; border: 2px solid var(--border-color); border-radius: var(--radius-sm); outline: none; font-weight: 700; flex-grow: 1; min-width: 0;">
                <button id="slide2-submit-btn" class="btn btn-primary" style="padding: 0.6rem 1.2rem; font-size: 1.1rem; border-radius: var(--radius-sm);">送出</button>
              </div>
              <p id="slide2-form-error" class="error-msg" style="margin-top: 0.4rem; text-align: left; font-size: 0.95rem; color: #E53E3E; font-weight: bold; display: none;"></p>
              <p id="slide2-success-msg" style="color: #38A169; font-weight: bold; margin-top: 0.4rem; font-size: 0.95rem; display: none;">✓ 送出成功！請看右側文字雲！</p>
            </div>

            <div class="interactive-status" style="margin-top: 0.8rem; display: flex; align-items: center; justify-content: space-between;">
              <p class="font-small font-bold" style="font-size: 1.05rem;">收到回應數：<span id="response-count" class="emphasis">0</span></p>
              <button id="clear-words-btn" class="btn btn-secondary" style="padding: 0.4rem 0.8rem; font-size: 0.9rem;">清空單字</button>
            </div>
          </div>
          <div class="right-col wc-container" style="height: 90%;">
            <!-- 文字雲繪製畫布 -->
            <canvas id="word-cloud-canvas"></canvas>
            <div id="word-cloud-placeholder" class="wc-placeholder">
              等待學生輸入回答...
            </div>
          </div>
        </div>
      </section>
"""

    # 3. Dark Contrast Slide Layout (Slide 3)
    elif stype == 'dark-slide':
        items = re.findall(r'^[*+-]\s+\*\*([^\*]+)\*\*：(.*)$', body_text, re.MULTILINE)
        left_char, left_word = "簡", "POWER"
        right_char, right_word = "報", "POINT"

        if len(items) >= 2:
            # 格式：* **簡 (POWER)**：描述文字
            left_title = items[0][0].strip()
            right_title = items[1][0].strip()

            # 從標題解析出字元與單字
            l_match = re.match(r'([^\(]+)\s*\(([^\)]+)\)', left_title)
            if l_match:
                left_char = l_match.group(1).strip()
                left_word = l_match.group(2).strip()
            r_match = re.match(r'([^\(]+)\s*\(([^\)]+)\)', right_title)
            if r_match:
                right_char = r_match.group(1).strip()
                right_word = r_match.group(2).strip()

        tag_category_html = f'<div class="tag-category">{current_theme}</div>' if current_theme else ""

        return f"""
      <!-- Slide {idx}: 第一單元 - 表達是靈魂 (黑底極簡對比風格) (由 MD 自動編譯) -->
      <section class="slide dark-slide" id="slide-{idx}">
        <div class="slide-content center-content">
          {tag_category_html}
          <div class="dark-slide-layout">
            <div class="dark-slide-col">
              <div class="dark-slide-char">{left_char}</div>
              <div class="dark-slide-word text-gold">{left_word}</div>
            </div>
            <div class="dark-slide-col">
              <div class="dark-slide-char">{right_char}</div>
              <div class="dark-slide-word">{right_word}</div>
            </div>
          </div>
        </div>
      </section>
"""

    # 4. Interactive NG Slide Layout
    elif stype == 'ng-game':
        tag_category_html = f'<div class="tag-category">{current_theme}</div>' if current_theme else ""
        return f"""
      <!-- Slide {idx}: 互動挑戰 - 簡報糾錯找不同 (由 MD 自動編譯) -->
      <section class="slide{active_class}" id="slide-{idx}">
        <div class="slide-content full-layout">
          {tag_category_html}
          <h2 class="slide-heading text-center">{apply_formatting(title)}</h2>
          <p class="text-center font-medium margin-bottom-sm">下面這是一張青少年製作的「感恩大自然」NG投影片，請找出 <span class="emphasis font-bold">4 個嚴重錯誤</span>！</p>

          <div class="game-container">
            <!-- NG 投影片本體 -->
            <div class="ng-slide-canvas" id="ng-slide">
              <div class="ng-header clickable-element" data-error="title" title="點擊檢查標題">
                感恩大自然投影片簡報!!!
              </div>
              <div class="ng-layout-body">
                <div class="ng-leftclickable clickable-element" data-error="text" title="點擊檢查左側文字">
                  <h3>一、大自然對我們的恩惠</h3>
                  <p>大自然給了我們新鮮的空氣，我們每天吸入的氧氣都是植物製造的，如果沒有植物，我們人類就會窒息而死。然後大自然還給了我們乾淨的水，水是生命之源，我們身體有70%都是水組成的。還有還有，大自然還提供了各種好吃的食物，包括米飯、蔬菜、水果、還有小麥，這些都是大自然慷慨賜予我們的，所以我們一定要好好感恩大自然，千萬不能破壞環境，否則會遭到大自然的報復喔！大家一定要記住！</p>
                </div>
                <div class="ng-rightclickable clickable-element" data-error="image" title="點擊檢查右側配圖">
                  <div class="ng-image-placeholder">
                    <span>一張超低畫質、有浮水印、而且歪掉的向日葵插圖</span>
                  </div>
                </div>
              </div>
              <div class="ng-footer clickable-element" data-error="style" title="點擊檢查整體風格">
                背景使用超刺眼的螢光綠漸層 ＋ 紅色新細明體 ＋ 閃爍彩虹字
              </div>
            </div>

            <!-- 錯誤說明面板 -->
            <div class="game-feedback-panel" id="game-feedback">
              <div class="feedback-title font-bold">點擊左側投影片中的錯誤區域進行糾錯！</div>
              <div class="feedback-body" id="feedback-text">
                請用滑鼠或手指點選 NG 投影片中有問題的地方。
              </div>
              <div class="found-counter">
                已尋找錯誤：<span id="found-count" class="emphasis">0</span> / 4
              </div>
              <button id="purify-btn" class="btn btn-primary btn-disabled" disabled>✨ 一鍵淨化簡報</button>
            </div>
          </div>
        </div>
      </section>
"""

    # 5. PDF Export Guide Layout
    elif stype == 'pdf-guide':
        # 解析 3 個步驟
        items = re.findall(r'^\d+\.\s+\*\*([^\*]+)\*\*：(.*)$', body_text, re.MULTILINE)
        cards_html = ""
        num_badges = ["01", "02", "03"]
        for i, item in enumerate(items[:3]):
            card_title = item[0].strip()
            card_desc = apply_formatting(item[1].strip()).replace("<br>", "<br>")
            # 支援換行符號 <br>
            cards_html += f"""
            <div class="grid-card">
              <div class="num-badge">{num_badges[i]}</div>
              <h3 class="font-bold">{card_title}</h3>
              <p class="font-small">{card_desc}</p>
            </div>"""

        highlight = "本簡報已內建 @media print 列印專用樣式。列印時會自動隱藏按鈕、輸入框及控制器，只留下乾淨的簡報內容。"
        hl_match = re.search(r'^>\s*💡\s*(.*)$', body_text, re.MULTILINE)
        if hl_match:
            highlight = apply_formatting(hl_match.group(1).strip())

        tag_category_html = f'<div class="tag-category">{current_theme}</div>' if current_theme else ""

        return f"""
      <!-- Slide {idx}: HTML 實作與 PDF 匯出指南 (由 MD 自動編譯) -->
      <section class="slide{active_class}" id="slide-{idx}">
        <div class="slide-content text-left-layout">
          {tag_category_html}
          <h2 class="slide-heading">{apply_formatting(title)}</h2>
          <p class="font-medium">如果學校或佛堂規定要交 PDF 格式，可以透過瀏覽器一鍵匯出：</p>

          <div class="grid-three-cols margin-top-md">
            {cards_html}
          </div>

          <div class="highlight-box font-small margin-top-sm">
            💡 {highlight}
          </div>
        </div>
      </section>
"""

    # 6. Center Quote Summary Layout (Slide 9)
    elif stype == 'center-quote':
        subtitle_match = re.search(r'^##\s+(.*)$', body_text, re.MULTILINE)
        subtitle = subtitle_match.group(1).strip() if subtitle_match else ""
        subtitle_html = apply_formatting(subtitle)

        points = re.findall(r'^[*+-]\s+(.*)$', body_text, re.MULTILINE)
        points_html = ""
        for i, pt in enumerate(points):
            points_html += f"""
            <div class="summary-point">
              <span class="num">{i+1}</span>
              <div class="summary-text">{apply_formatting(pt.strip())}</div>
            </div>"""

        quote = "「用最真誠的心，說溫暖人的故事。」—— 這是 AI 永遠學不會的事。"
        q_match = re.search(r'^>\s*💬\s*(.*)$', body_text, re.MULTILINE)
        if q_match:
            quote = apply_formatting(q_match.group(1).strip())

        return f"""
      <!-- Slide {idx}: 結論與行動 (由 MD 自動編譯) -->
      <section class="slide{active_class}" id="slide-{idx}">
        <div class="slide-content center-content">
          <div class="tag">本課總結</div>
          <h2 class="slide-heading font-huge">{subtitle_html}</h2>

          <div class="summary-points font-large margin-top-md">
            {points_html}
          </div>

          <div class="final-quote font-medium margin-top-md">
            {quote}
          </div>
        </div>
      </section>
"""

    # 7. QA Slide Layout
    elif stype == 'qa':
        return f"""
      <!-- Slide {idx}: 結尾金句頁 (由 MD 自動編譯) -->
      <section class="slide title-slide{active_class}" id="slide-{idx}">
        <div class="slide-content center-content">
          <h1 class="slide-title font-giant">{apply_formatting(title)}</h1>
        </div>
      </section>
"""

    # 8. Full Image Slide Layout
    elif stype == 'image-full':
        image_match = re.search(r'!\[([^\]]*)\]\(([^\)]+)\)', text)
        if image_match:
            img_alt = image_match.group(1)
            img_src = image_match.group(2)
        else:
            img_alt = title
            img_src = ""
        return f"""
      <!-- Slide {idx}: 全頁圖片 (由 MD 自動編譯) -->
      <section class="slide image-full-slide{active_class}" id="slide-{idx}">
        <img src="{img_src}" alt="{img_alt}" class="full-slide-image">
      </section>
"""

    # 9. General Bullet List Slide Layout (Slides 4, 5, 6)
    else:
        # 尋找第一行文字作為 description（如果不是列表）
        lines = body_text.split('\n')
        desc_lines = []
        list_start_idx = 0
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            if line.startswith('*') or line.startswith('-') or line.startswith('1.') or line.startswith('>') or line.startswith('!'):
                list_start_idx = i
                break
            desc_lines.append(line)

        desc = " ".join(desc_lines)
        desc_html = f'<p class="bullet-desc-intro">{apply_formatting(desc)}</p>' if desc else ""

        remaining_text = "\n".join(lines[list_start_idx:])

        # 1. 列表解析
        bullet_items = re.findall(r'^[*+-]\s+(.*)$', remaining_text, re.MULTILINE)
        num_items = re.findall(r'^\d+\.\s+(.*)$', remaining_text, re.MULTILINE)

        list_html = ""
        grid_html = ""

        # 判斷是否為 3 欄式卡片（Slide 5, Slide 6 的排版特徵）
        # 如果列表中包含 **標題** 且有引導內容，我們把它渲染為 grid-card
        if len(num_items) == 3:
            grid_html = '<div class="grid-three-cols margin-top-md">'
            for i, item in enumerate(num_items):
                item = item.strip()
                # 格式：**標題**：描述文字
                card_title_match = re.match(r'^\*\*([^\*]+)\*\*：(.*)$', item)
                if card_title_match:
                    c_title = card_title_match.group(1).strip()
                    c_desc = apply_formatting(card_title_match.group(2).strip())
                else:
                    c_title = f"原則 {i+1}"
                    c_desc = apply_formatting(item)

                grid_html += f"""
            <div class="grid-card">
              <div class="num-badge">0{i+1}</div>
              <h3 class="font-bold">{c_title}</h3>
              <p class="font-small">{c_desc}</p>
            </div>"""
            grid_html += '</div>'

        elif stype == 'bullet-list' and len(bullet_items) == 3 and "1. " in remaining_text and "2. " in remaining_text:
            # 針對 Slide 6 法寶卡片特殊排版 (1. 2. 3.)
            # 特徵：* **1. 標題**：描述文字
            grid_html = '<div class="grid-three-cols margin-top-md">'
            icons = ["⚡", "3️⃣", "🖼️"]
            for i, item in enumerate(bullet_items):
                item = item.strip()
                card_title_match = re.match(r'^\*\*([^\*]+)\*\*：(.*)$', item)
                if card_title_match:
                    c_title = card_title_match.group(1).strip()
                    c_desc = apply_formatting(card_title_match.group(2).strip())
                else:
                    c_title = f"法寶 {i+1}"
                    c_desc = apply_formatting(item)

                grid_html += f"""
            <div class="principle-card">
              <div class="card-icon">{icons[i]}</div>
              <h3>{c_title}</h3>
              <p class="font-small">{c_desc}</p>
            </div>"""
            grid_html += '</div>'

        else:
            # 一般清單排版：統一使用 ✦ 星號，支援兩行格式（**標題**：說明）
            items_to_render = bullet_items if bullet_items else num_items
            if items_to_render:
                list_html = '<ul class="bullet-list-v2">'
                for item in items_to_render:
                    item = item.strip()
                    title_desc_match = re.match(r'^\*\*([^\*]+)\*\*[：:]\s*(.+)$', item)
                    if title_desc_match:
                        b_title = title_desc_match.group(1).strip()
                        b_desc = apply_formatting(title_desc_match.group(2).strip())
                        list_html += f'<li><div class="bullet-title">{b_title}</div><div class="bullet-desc">{b_desc}</div></li>'
                    else:
                        list_html += f'<li><div class="bullet-title">{apply_formatting(item)}</div></li>'
                list_html += '</ul>'

        # 2. 高亮引用框或範例卡片解析
        highlight_html = ""
        slogan_grid_html = ""

        # 尋找 blockquote
        bq_match = re.search(r'^>\s*💡\s*\*\*([^\*]+)\*\*(.*)$', remaining_text, re.MULTILINE)
        if bq_match:
            bq_title = bq_match.group(1).strip()
            examples_text = remaining_text[bq_match.end():].strip()
            examples_clean = "\n".join([re.sub(r'^>\s*', '', line) for line in examples_text.split('\n')])
            example_items = re.findall(r'^[*+-]\s+(.*)$', examples_clean, re.MULTILINE)
            if example_items:
                grid_cols = len(example_items)
                slogan_grid_html = f"""
          <div class="slogan-examples margin-top-md">
            <p class="font-small font-bold">{bq_title}</p>
            <div class="example-grid" style="grid-template-columns: repeat({grid_cols}, 1fr);">"""
                for item in example_items:
                    slogan_grid_html += f'<div class="example-item">{apply_formatting(item.strip())}</div>'
                slogan_grid_html += """
            </div>
          </div>"""
        else:
            # 一般的 highlight-box
            bq_simple = re.search(r'^>\s*💡\s*(.*)$', remaining_text, re.MULTILINE)
            if bq_simple:
                highlight_html = f"""
          <div class="highlight-box font-medium margin-top-md">
            💡 {apply_formatting(bq_simple.group(1).strip())}
          </div>"""

        # 圖片解析（抓出 ![alt](src) 並轉換為 HTML）
        image_html = ""
        image_matches = re.findall(r'!\[([^\]]*)\]\(([^\)]+)\)', remaining_text)
        if image_matches:
            image_html = ""
            for alt, src in image_matches:
                image_html += f'<img src="{src}" alt="{alt}" style="max-width:100%; max-height:320px; border-radius:8px; margin: 0.8rem auto; display:block;">'

        # 合併所有的排版模組
        content_html = f"{desc_html}\n{list_html}\n{grid_html}\n{slogan_grid_html}\n{highlight_html}\n{image_html}"

        tag_category_html = f'<div class="tag-category">{current_theme}</div>' if current_theme else ""

        return f"""
      <!-- Slide {idx}: (由 MD 自動編譯) -->
      <section class="slide{active_class}" id="slide-{idx}">
        <div class="slide-content text-left-layout">
          {tag_category_html}
          <h2 class="slide-heading">{apply_formatting(title)}</h2>
          {content_html}
        </div>
      </section>
"""

def compile_presentation():
    # 決定檔案路徑
    current_dir = os.path.dirname(os.path.abspath(__file__))
    course_name = os.path.basename(current_dir)

    # Obsidian 庫的基礎路徑
    obsidian_base_dir = r"G:\我的雲端硬碟\00_個人大腦同步區\Obsidian\💼 30_專案與備課\31_講課備課思維"

    # 自動搜尋：優先找 📌 進行中，再找 📦 備課庫
    md_file = None
    for subdir in ["📌 進行中", "📦 備課庫"]:
        candidate = os.path.join(obsidian_base_dir, subdir, f"{course_name}_簡報.md")
        if os.path.exists(candidate):
            md_file = candidate
            break

    if not md_file:
        print(f"❌ 找不到簡報檔案：請確認 {course_name}_簡報.md 在 📌 進行中 或 📦 備課庫 資料夾中")
        return

    output_file = os.path.join(current_dir, f"{course_name}_簡報.html")
    template_file = os.path.join(current_dir, "index.template.html")

    print("=================== HTML簡報編譯器 ===================")
    print(f"目前課程專案名稱：{course_name}")
    print(f"1. 讀取備課 Markdown：{md_file}")
    slides = parse_markdown_slides(md_file)
    print(f"   共解析出 {len(slides)} 頁投影片。")

    # 生成投影片 HTML
    compiled_slides_html = []
    current_theme = ""
    for slide in slides:
        stype = slide['type']
        text = slide['raw_text']

        # 如果是轉場頁，更新當前主題名稱
        if stype == 'theme-title':
            title_match = re.search(r'^#\s+(.*)$', text, re.MULTILINE)
            if title_match:
                current_theme = title_match.group(1).strip()

        print(f"   -> 編譯第 {slide['index']} 頁: [{stype}] (主題: {current_theme})")
        slide_html = build_slide_html(slide, current_theme)
        compiled_slides_html.append(slide_html)

    slides_content = "\n".join(compiled_slides_html)

    # 載入模板並注入內容
    if not os.path.exists(template_file):
        print(f"❌ 錯誤：找不到簡報模板檔案 {template_file}")
        return

    with open(template_file, 'r', encoding='utf-8') as f:
        template_content = f.read()

    # 置換佔位符
    final_html = template_content.replace("<!-- SLIDES_PLACEHOLDER -->", slides_content)

    # 同步修改總頁數顯示 (導航列)
    total_slides = len(slides)
    final_html = re.sub(
        r'<span id="slide-number-display">.*?</span>',
        f'<span id="slide-number-display">1 / {total_slides}</span>',
        final_html
    )

    # 寫入產出的 index.html
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_html)

    print(f"2. 成功輸出簡報檔案：{output_file}")
    print(f"")
    print(f"⚠️  上傳 GitHub Pages 前，請先將 {course_name}_簡報.html 改名為 index.html")

    # 同步修改 app.js 中的總頁數變數
    app_js_path = os.path.join(current_dir, "app.js")
    if os.path.exists(app_js_path):
        with open(app_js_path, 'r', encoding='utf-8') as f:
            app_js_content = f.read()
        # 把 totalSlides: \d+ 替換為實際的投影片數量
        updated_app_js = re.sub(r'totalSlides:\s*\d+', f'totalSlides: {total_slides}', app_js_content)
        with open(app_js_path, 'w', encoding='utf-8') as f:
            f.write(updated_app_js)
        print(f"3. 同步修改 app.js 總頁數變數：{total_slides} 頁。")

    print("編譯完成！")

if __name__ == "__main__":
    compile_presentation()
